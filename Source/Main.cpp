#include <SDL.h>
#include <nlohmann/json.hpp>
#include "Game.hpp"
#include "Platform.hpp"
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <fstream>
#include <map>
#include <memory>
#include <string>
#include <vector>

using namespace bo2cs;
using json=nlohmann::json;
namespace {
Game game;
SDL_Window* window=nullptr;
SDL_Renderer* renderer=nullptr;
SDL_AudioDeviceID audio=0;
SDL_GameController* controller=nullptr;
std::ofstream logfile;
std::string logs;
int width=960,height=440;
float insetL=0,insetR=0,insetT=0,insetB=0;
bool playing=false,paused=false,debug=true,scoreboard=false,autotest=false,running=true,crouched=false;
float sensitivity=2.5f,opacity=.5f,jumpTime=0;
int layout=0;
unsigned long frames=0,drawCalls=0;
double worst=0,total=0,loadMilliseconds=0;
bool playerSpawned=false,worldReady=false;
std::map<SDL_FingerID,SDL_FPoint> touches;
SDL_FingerID moveFinger=-1,lookFinger=-1;
SDL_FPoint movementOrigin{},movement{};
std::vector<float> depth;
struct Button { std::string name;SDL_Rect rect; };
std::vector<Button> buttons;
void log(const std::string& stage) {std::string line=std::to_string(SDL_GetTicks64())+" "+stage;std::printf("%s\n",line.c_str());std::fflush(stdout);logfile<<line<<'\n';logfile.flush();}
void color(int r,int g,int b,int a=255){SDL_SetRenderDrawColor(renderer,Uint8(r),Uint8(g),Uint8(b),Uint8(a));}
void rect(int x,int y,int w,int h){SDL_Rect r{x,y,w,h};SDL_RenderFillRect(renderer,&r);++drawCalls;}
// Original compact bitmap alphabet, rendered without external font assets.
const std::map<char,std::string> font={
{'A',"01110100011000111111100011000110001"},{'B',"11110100011000111110100011000111110"},
{'C',"01111100001000010000100001000001111"},{'D',"11110100011000110001100011000111110"},
{'E',"11111100001000011110100001000011111"},{'F',"11111100001000011110100001000010000"},
{'G',"01111100001000010111100011000101111"},{'H',"10001100011000111111100011000110001"},
{'I',"11111001000010000100001000010011111"},{'J',"00111000100001000010100101001001100"},
{'K',"10001100101010011000101001001010001"},{'L',"10000100001000010000100001000011111"},
{'M',"10001110111010110101100011000110001"},{'N',"10001110011010110011100011000110001"},
{'O',"01110100011000110001100011000101110"},{'P',"11110100011000111110100001000010000"},
{'Q',"01110100011000110001101011001001101"},{'R',"11110100011000111110101001001010001"},
{'S',"01111100001000001110000010000111110"},{'T',"11111001000010000100001000010000100"},
{'U',"10001100011000110001100011000101110"},{'V',"10001100011000110001100010101000100"},
{'W',"10001100011000110101101011101110001"},{'X',"10001100010101000100010101000110001"},
{'Y',"10001100010101000100001000010000100"},{'Z',"11111000010001000100010001000011111"},
{'0',"01110100011001110101110011000101110"},{'1',"00100011000010000100001000010001110"},
{'2',"01110100010000100010001000100011111"},{'3',"11110000010000101110000010000111110"},
{'4',"00010001100101010010111110001000010"},{'5',"11111100001000011110000010000111110"},
{'6',"01110100001000011110100011000101110"},{'7',"11111000010001000100010000100001000"},
{'8',"01110100011000101110100011000101110"},{'9',"01110100011000101111000010000101110"},
{':',"00000001000010000000001000010000000"},{'-',"00000000000000011111000000000000000"},
{'.',"00000000000000000000000000010000100"},{'/',"00001000100001000100010000100010000"}};
void text(const std::string& value,int x,int y,int scale=2){
    for(char c:value){auto it=font.find(c);if(it!=font.end())for(int row=0;row<7;++row)for(int col=0;col<5;++col)if(it->second[row*5+col]=='1')rect(x+col*scale,y+row*scale,scale,scale);x+=6*scale;}
}
void layoutButtons(){
    SDL_GetWindowSize(window,&width,&height);SDL_RenderSetLogicalSize(renderer,width,height);
    safeInsets(insetL,insetR,insetT,insetB);
    buttons.clear();int bw=std::max(54,std::min(76,(width-int(insetL+insetR))/11)),bh=38;
    const char* names[]={"FIRE","RELOAD","JUMP","CROUCH","USE","SWAP","SCORE","PAUSE"};
    int right=width-int(insetR)-12, bottom=height-int(insetB)-12;
    for(int i=0;i<8;++i)buttons.push_back({names[i],{right-(4-i%4)*(bw+6),bottom-(2-i/4)*(bh+6)-layout*20,bw,bh}});
}
bool inside(SDL_FPoint p,SDL_Rect r){return p.x>=r.x&&p.y>=r.y&&p.x<r.x+r.w&&p.y<r.y+r.h;}
void saveSettings(){std::ofstream(logs+"/../Controls.json")<<json{{"sensitivity",sensitivity},{"opacity",opacity},{"layout",layout}};}
void fire(){if(game.fire(0)){game.actors[0].angle+=game.weapon.recoil;if(audio){std::vector<Sint16> samples(1800);for(size_t i=0;i<samples.size();++i)samples[i]=Sint16(std::sin(i*.19)*4500*(1-float(i)/samples.size()));SDL_QueueAudio(audio,samples.data(),Uint32(samples.size()*sizeof(Sint16)));}}}
void event(const SDL_Event& e){
    if(e.type==SDL_QUIT)running=false;
    if(e.type==SDL_WINDOWEVENT&&e.window.event==SDL_WINDOWEVENT_SIZE_CHANGED)layoutButtons();
    if(e.type==SDL_FINGERDOWN){
        SDL_FPoint p{e.tfinger.x*width,e.tfinger.y*height};touches[e.tfinger.fingerId]=p;
        if(!playing){playing=true;log("GAME_LOOP_ACTIVE");return;}
        if(paused){
            if(p.y<height*.4f){paused=false;return;}
            if(p.y<height*.55f){sensitivity=sensitivity>=4?1:sensitivity+.5f;}
            else if(p.y<height*.7f){opacity=opacity>=.8f?.3f:opacity+.1f;}
            else if(p.y<height*.85f){layout=1-layout;layoutButtons();}
            else shareLogs();saveSettings();return;
        }
        for(auto& b:buttons)if(inside(p,b.rect)){
            if(b.name=="RELOAD")game.reload(0);if(b.name=="JUMP")jumpTime=.6f;if(b.name=="CROUCH")crouched=!crouched;
            if(b.name=="SCORE")scoreboard=!scoreboard;if(b.name=="PAUSE")paused=true;
            if(b.name=="SWAP")log("WEAPON_SWITCH single prototype carbine");
            return;
        }
        if(p.x<width*.4f&&moveFinger==-1){moveFinger=e.tfinger.fingerId;movementOrigin=p;}
        else if(lookFinger==-1)lookFinger=e.tfinger.fingerId;
    }
    if(e.type==SDL_FINGERMOTION){
        SDL_FPoint p{e.tfinger.x*width,e.tfinger.y*height};touches[e.tfinger.fingerId]=p;
        if(e.tfinger.fingerId==moveFinger)movement={std::clamp((p.x-movementOrigin.x)/55.f,-1.f,1.f),std::clamp((p.y-movementOrigin.y)/55.f,-1.f,1.f)};
        if(e.tfinger.fingerId==lookFinger&&!paused)game.actors[0].angle+=e.tfinger.dx*sensitivity*3;
    }
    if(e.type==SDL_FINGERUP){touches.erase(e.tfinger.fingerId);if(e.tfinger.fingerId==moveFinger){moveFinger=-1;movement={};}if(e.tfinger.fingerId==lookFinger)lookFinger=-1;}
    if(e.type==SDL_CONTROLLERDEVICEADDED&&!controller)controller=SDL_GameControllerOpen(e.cdevice.which);
    if(e.type==SDL_CONTROLLERDEVICEREMOVED&&controller){SDL_GameControllerClose(controller);controller=nullptr;}
}
void input(float dt){
    auto& p=game.actors[0];SDL_FPoint motion=movement;
    if(controller){motion={SDL_GameControllerGetAxis(controller,SDL_CONTROLLER_AXIS_LEFTX)/32767.f,SDL_GameControllerGetAxis(controller,SDL_CONTROLLER_AXIS_LEFTY)/32767.f};if(std::abs(motion.x)<.15f)motion.x=0;if(std::abs(motion.y)<.15f)motion.y=0;
        p.angle+=SDL_GameControllerGetAxis(controller,SDL_CONTROLLER_AXIS_RIGHTX)/32767.f*dt*sensitivity;
        if(SDL_GameControllerGetAxis(controller,SDL_CONTROLLER_AXIS_TRIGGERRIGHT)>8000)fire();
        if(SDL_GameControllerGetButton(controller,SDL_CONTROLLER_BUTTON_X))game.reload(0);
        if(SDL_GameControllerGetButton(controller,SDL_CONTROLLER_BUTTON_A))game.interact(0,dt);
    }
    game.move(p,{std::cos(p.angle)*-motion.y-std::sin(p.angle)*motion.x,std::sin(p.angle)*-motion.y+std::cos(p.angle)*motion.x},dt*(crouched?.5f:1));
    bool usingObjective=false;
    for(auto& [id,point]:touches)for(auto& b:buttons)if(inside(point,b.rect)){
        if(b.name=="FIRE")fire();if(b.name=="USE"){game.interact(0,dt);usingObjective=true;}
    }
    if(!usingObjective&&!controller)p.interaction=0;
}
void world(){
    int camera=0;if(!game.actors[0].alive)for(int i=1;i<3;++i)if(game.actors[i].alive){camera=i;break;}
    auto& p=game.actors[camera];
    int horizon=height/2+int(std::sin(jumpTime*5.23f)*35)-(crouched?25:0);
    color(34,51,70);rect(0,0,width,horizon);color(52,56,57);rect(0,horizon,width,height-horizon);
    const int columns=std::min(width,400);depth.assign(columns,30);
    for(int i=0;i<columns;++i){
        float offset=(float(i)/columns-.5f)*1.15f,angle=p.angle+offset,d=.02f;
        for(;d<30;d+=.035f)if(!game.map.walkable(p.position.x+std::cos(angle)*d,p.position.y+std::sin(angle)*d))break;
        float corrected=std::max(.05f,d*std::cos(offset));depth[i]=corrected;int wh=int(height/corrected);
        float wx=p.position.x+std::cos(angle)*d,wy=p.position.y+std::sin(angle)*d;
        int shade=int(160/(1+corrected*.12f));bool stripe=(int(wx*4)+int(wy*4))%2;
        color(shade,stripe?shade:shade*9/10,shade*8/10);rect(i*width/columns,horizon-wh/2,width/columns+1,wh);
        color(shade/2,shade/2,shade/2);rect(i*width/columns,horizon+wh/2-2,width/columns+1,2);
    }
    std::vector<int> order;for(int i=0;i<int(game.actors.size());++i)if(i!=camera&&game.actors[i].alive)order.push_back(i);
    std::sort(order.begin(),order.end(),[&](int a,int b){return (game.actors[a].position-p.position).length()>(game.actors[b].position-p.position).length();});
    for(int i:order){auto& a=game.actors[i];Vec delta=a.position-p.position;float angle=std::atan2(delta.y,delta.x)-p.angle;
        while(angle>3.14159f)angle-=6.28318f;while(angle< -3.14159f)angle+=6.28318f;
        float d=delta.length()*std::cos(angle);if(std::abs(angle)>.7f||d<.2f)continue;
        int x=int((angle/1.15f+.5f)*width),h=int(height/d*.75f),w=h/3;
        for(int sx=std::max(0,x-w/2);sx<std::min(width,x+w/2);++sx)if(d<depth[std::min(columns-1,sx*columns/width)]){
            if(a.team)color(70,160,230);else color(230,160,60);rect(sx,horizon-h/2,1,h);color(205,179,147);rect(sx,horizon-h/2,1,h/5);
        }
    }
    color(190,199,207);rect(width/2+20,height-100,45,100);color(49,55,62);rect(width/2+12,height-105,25,90);
    if(game.actors[0].cooldown>.12f){color(255,225,100);rect(width/2+7,height-130,34,28);}
    color(240,240,225);rect(width/2-8,height/2,16,1);rect(width/2,height/2-8,1,16);
}
void hud(){
    auto& p=game.actors[0];int left=int(insetL)+12,top=int(insetT)+12;
    color(245,235,210);text("BO2CS  A "+std::to_string(game.scores[0])+" - "+std::to_string(game.scores[1])+" D",left,top);
    text("TIME "+std::to_string(int(std::max(0.f,game.remaining))),width/2-60,top);
    text("HP "+std::to_string(int(p.health))+" ARM "+std::to_string(int(p.armor))+" AMMO "+std::to_string(p.ammo),left,top+22);
    if(game.planted){color(255,120,70);text("BOMB "+std::to_string(int(game.bombTime)),width/2-60,top+24);}
    if(!p.alive)text("SPECTATING - NEXT ROUND",width/2-145,height/3);
    if(game.winner!=-1)text(game.winner?"DEFENSE WINS":"ATTACK WINS",width/2-85,height/3+30,2);
    for(auto& b:buttons){color(10,18,28,int(opacity*255));rect(b.rect.x,b.rect.y,b.rect.w,b.rect.h);color(235,240,245);text(b.name,b.rect.x+5,b.rect.y+14,1);}
    color(130,170,190,100);rect(left+20,height-int(insetB)-120,90,90);color(200,230,240,180);rect(left+57+int(movement.x*35),height-int(insetB)-83+int(movement.y*35),16,16);
    if(debug){color(180,240,180);text("FPS "+std::to_string(total>0?int(frames/total):0)+" DRAW "+std::to_string(drawCalls)+" TEX 0 MESH 0",left,top+45,1);text("MEM "+std::to_string(int(residentMemoryMB()))+" MB",left,top+57,1);}
    if(scoreboard){color(10,20,30,235);rect(width/2-150,70,300,220);color(230,230,220);text("ROUND "+std::to_string(game.round),width/2-125,85);for(int i=0;i<int(game.actors.size());++i)text(std::string(i?"BOT ":"YOU ")+std::to_string(i)+" KILLS "+std::to_string(game.actors[i].kills),width/2-125,115+i*24,2);}
    if(paused){color(8,16,24,245);rect(0,0,width,height);color(230,230,220);text("PAUSED - TAP TO RESUME",width/2-160,height/4);text("SENSITIVITY "+std::to_string(int(sensitivity*10)),width/2-160,int(height*.45f));text("OPACITY "+std::to_string(int(opacity*100)),width/2-160,int(height*.6f));text("CONTROL LAYOUT "+std::to_string(layout),width/2-160,int(height*.75f));text("EXPORT LOGS",width/2-160,int(height*.9f));}
}
}
int main(int argc,char** argv){
    logs=logDirectory();logfile.open(logs+"/runtime.log",std::ios::trunc);log("APP_START");log("FILESYSTEM_INIT");
    autotest=SDL_getenv("AUTOTEST")&&std::string(SDL_getenv("AUTOTEST"))=="1";
    try {
        std::ifstream settings(logs+"/../Controls.json");if(settings){json j;settings>>j;sensitivity=std::clamp(j.value("sensitivity",2.5f),.5f,5.f);opacity=std::clamp(j.value("opacity",.5f),.2f,.9f);layout=std::clamp(j.value("layout",0),0,1);}
        if(SDL_Init(SDL_INIT_VIDEO|SDL_INIT_AUDIO|SDL_INIT_GAMECONTROLLER)!=0)throw std::runtime_error(SDL_GetError());
        SDL_SetHint(SDL_HINT_RENDER_DRIVER,"metal");
        window=SDL_CreateWindow("BO2CS",0,0,width,height,SDL_WINDOW_FULLSCREEN_DESKTOP|SDL_WINDOW_ALLOW_HIGHDPI);
        if(!window)throw std::runtime_error(SDL_GetError());
        renderer=SDL_CreateRenderer(window,-1,SDL_RENDERER_ACCELERATED|SDL_RENDERER_PRESENTVSYNC);
        if(!renderer)throw std::runtime_error(SDL_GetError());
        SDL_RendererInfo ri;SDL_GetRendererInfo(renderer,&ri);log(std::string("RENDERER_INIT backend=")+ri.name);
        SDL_SetRenderDrawBlendMode(renderer,SDL_BLENDMODE_BLEND);layoutButtons();log("INPUT_INIT multitouch safe-area controller");
        SDL_AudioSpec requested{};requested.freq=48000;requested.format=AUDIO_S16SYS;requested.channels=1;requested.samples=1024;
        audio=SDL_OpenAudioDevice(nullptr,0,&requested,nullptr,0);if(audio){SDL_PauseAudioDevice(audio,0);log("AUDIO_INIT");}else log(std::string("AUDIO_UNAVAILABLE ")+SDL_GetError());
        auto loading=SDL_GetPerformanceCounter();log("GAMEDATA_INIT");log("MAP_LOAD_BEGIN original validation map");
        game.load(resourceDirectory()+"/GameData/validation.map.json",resourceDirectory()+"/GameData/weapons.json");
        loadMilliseconds=1000.*(SDL_GetPerformanceCounter()-loading)/SDL_GetPerformanceFrequency();
        worldReady=true;log("MAP_GEOMETRY_READY grid raycaster");log("COLLISION_READY");playerSpawned=game.actors[0].alive;log("PLAYER_SPAWNED");log("BOTS_SPAWNED count=5");log("MAIN_MENU_READY");
        if(autotest){Actor probe=game.actors[0];probe.position={1.3f,1.3f};game.move(probe,{-1,0},1);}
        Uint64 previous=SDL_GetPerformanceCounter(),start=previous;unsigned long lastHeartbeat=0;
        while(running){
            Uint64 now=SDL_GetPerformanceCounter();double realDt=double(now-previous)/SDL_GetPerformanceFrequency();previous=now;
            double elapsed=double(now-start)/SDL_GetPerformanceFrequency();float dt=float(std::min(realDt,.1));
            SDL_Event e;while(SDL_PollEvent(&e))event(e);
            if(autotest&&elapsed>1&&!playing){playing=true;log("GAME_LOOP_ACTIVE");}
            if(playing&&!paused){if(!autotest)input(dt);game.update(dt,autotest);jumpTime=std::max(0.f,jumpTime-dt);}
            drawCalls=0;color(5,12,20);SDL_RenderClear(renderer);
            if(playing){world();hud();}else{color(240,230,200);text("BO2CS",width/2-90,height/3,6);text("ORIGINAL TACTICAL PROTOTYPE",width/2-155,height/2);text("TAP TO PLAY",width/2-70,height*2/3);}
            SDL_RenderPresent(renderer);++frames;total+=realDt;worst=std::max(worst,realDt);
            if(frames-lastHeartbeat>=120){lastHeartbeat=frames;log("FRAME frames="+std::to_string(frames)+" bots="+std::to_string(game.botUpdates)+" shots="+std::to_string(game.shots)+" round="+std::to_string(game.round));}
            if(autotest&&elapsed>=61){
                bool pass=worldReady&&playerSpawned&&frames>=60&&game.actors.size()==6&&game.botUpdates>100&&game.shots>0&&game.hits>0&&game.movements>0&&game.collisionBlocks>0;
                json result={{"status",pass?"PASS":"FAIL"},{"passed",pass},{"duration_seconds",elapsed-1},{"frames",frames},{"player_spawned",playerSpawned},{"world_ready",worldReady},{"bot_updates",game.botUpdates},{"shots",game.shots},{"hits",game.hits},{"movements",game.movements},{"collision_blocks",game.collisionBlocks},{"round",game.round},{"plants",game.plants},{"defuses",game.defuses},{"entity_count",game.actors.size()},{"average_frame_ms",total*1000/frames},{"worst_frame_ms",worst*1000},{"memory_mb",residentMemoryMB()},{"loaded_textures",0},{"loaded_meshes",0},{"loaded_grid_maps",1},{"map_load_ms",loadMilliseconds},{"asset_load_ms",loadMilliseconds},{"draw_calls_last_frame",drawCalls},{"performance_scope","simulator only"},{"exit_reason","clean SDL shutdown requested"},{"asset_kind","original synthetic fixture, not PS3"}};
                result["run_id"]=SDL_getenv("AUTOTEST_RUN_ID")?SDL_getenv("AUTOTEST_RUN_ID"):"local";
                std::ofstream(logs+"/AUTOTEST_RESULT.tmp")<<result.dump(2);
                std::rename((logs+"/AUTOTEST_RESULT.tmp").c_str(),(logs+"/AUTOTEST_RESULT.json").c_str());
                log(pass?"AUTOTEST_PASS":"AUTOTEST_FAIL");running=false;
            }
            SDL_Delay(1);
        }
        if(controller)SDL_GameControllerClose(controller);if(audio)SDL_CloseAudioDevice(audio);SDL_DestroyRenderer(renderer);SDL_DestroyWindow(window);SDL_Quit();log("APP_EXIT clean");return 0;
    } catch(const std::exception& e){log(std::string("FATAL ")+e.what());if(autotest)std::ofstream(logs+"/AUTOTEST_RESULT.json")<<json{{"status","FAIL"},{"passed",false},{"reason",e.what()}}.dump(2);SDL_Quit();return 1;}
}
