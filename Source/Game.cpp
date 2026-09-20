#include "Game.hpp"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <fstream>
#include <queue>
#include <stdexcept>

namespace bo2cs {
using json=nlohmann::json;
bool Map::walkable(float x,float y) const {
    if (!std::isfinite(x)||!std::isfinite(y)||y<0||x<0||y>=rows.size()||rows.empty()||x>=rows[0].size()) return false;
    return rows[int(y)][int(x)]=='.';
}
bool Map::visible(Vec a,Vec b) const {
    auto delta=b-a;
    int steps=std::max(1,int(delta.length()/.05f));
    for(int i=0;i<=steps;++i) { auto p=a+delta*(float(i)/steps); if(!walkable(p.x,p.y)) return false; }
    return true;
}
Vec Map::nextStep(Vec from,Vec destination) const {
    if(visible(from,destination)) return destination;
    int w=int(rows[0].size()),h=int(rows.size());
    int start=int(from.y)*w+int(from.x), goal=int(destination.y)*w+int(destination.x);
    if(start<0||start>=w*h||goal<0||goal>=w*h) return from;
    std::vector<int> parent(w*h,-1); parent[start]=start;
    std::queue<int> q; q.push(start);
    while(!q.empty()&&parent[goal]==-1) {
        int p=q.front();q.pop();
        const int dx[]={1,-1,0,0},dy[]={0,0,1,-1};
        for(int d=0;d<4;++d) {
            int x=p%w+dx[d],y=p/w+dy[d],n=y*w+x;
            if(walkable(x+.5f,y+.5f)&&parent[n]==-1) {parent[n]=p;q.push(n);}
        }
    }
    if(parent[goal]==-1||goal==start) return from;
    int n=goal; while(parent[n]!=start)n=parent[n];
    return {n%w+.5f,n/w+.5f};
}
void Game::load(const std::string& path,const std::string& weaponPath) {
    std::ifstream mf(path),wf(weaponPath);
    if(!mf||!wf) throw std::runtime_error("missing required game data");
    json m,w;mf>>m;wf>>w;
    if(m.at("format")!="bo2cs.map.v1") throw std::runtime_error("unsupported runtime map");
    map.rows=m.at("rows").get<std::vector<std::string>>();
    if(map.rows.size()<4||map.rows.size()>128||map.rows[0].size()<4||map.rows[0].size()>128) throw std::runtime_error("invalid map size");
    for(auto& r:map.rows) if(r.size()!=map.rows[0].size()||r.find_first_not_of("#.")!=std::string::npos)throw std::runtime_error("invalid grid");
    map.scale=m.at("meters_per_cell");
    if(!std::isfinite(map.scale)||map.scale<.1f||map.scale>10) throw std::runtime_error("invalid scale");
    map.zone={m.at("plant_zone")[0],m.at("plant_zone")[1]};
    for(int team=0;team<2;++team) {
        map.spawns[team].clear();
        for(auto& p:m.at("spawns").at(team?"defense":"attack")) {
            Vec v{p[0],p[1]};if(!map.walkable(v.x,v.y))throw std::runtime_error("spawn in wall");map.spawns[team].push_back(v);
        }
        if(map.spawns[team].size()<3)throw std::runtime_error("missing team spawns");
    }
    weapon.damage=w.at("damage");weapon.fireRate=w.at("fire_rate");weapon.magazine=w.at("magazine_capacity");
    weapon.reserve=w.at("reserve_ammo");weapon.reloadDuration=w.at("reload_duration");weapon.spread=w.at("spread");weapon.recoil=w.at("recoil");
    if(weapon.damage<=0||weapon.fireRate<=0||weapon.magazine<1||weapon.reserve<0||weapon.reloadDuration<=0)throw std::runtime_error("invalid weapon");
    actors.resize(6);newRound();
}
void Game::newRound() {
    ++round;remaining=90;bombTime=20;planted=false;winner=-1;roundDelay=0;carrier=0;
    for(int i=0;i<int(actors.size());++i) {
        int kills=actors[i].kills;actors[i]=Actor{};auto& a=actors[i];a.kills=kills;a.team=i<3?0:1;
        a.position=map.spawns[a.team][i%3];a.angle=a.team?3.14159f:0;a.ammo=weapon.magazine;a.reserve=weapon.reserve;
    }
}
void Game::win(int team) {if(winner!=-1)return;winner=team;++scores[team];roundDelay=4;}
void Game::move(Actor& a,Vec d,float dt) {
    if(!a.alive||winner!=-1||dt<=0)return;
    if(d.length()>1)d=d*(1/d.length());
    float distance=2.4f*dt/map.scale;
    int steps=std::max(1,int(distance/.08f)+1);
    auto free=[&](Vec p){for(float x:{-.2f,.2f})for(float y:{-.2f,.2f})if(!map.walkable(p.x+x,p.y+y))return false;return true;};
    for(int i=0;i<steps;++i) {
        Vec p=a.position; p.x+=d.x*distance/steps;
        if(free(p)){if(p.x!=a.position.x)++movements;a.position.x=p.x;}else ++collisionBlocks;
        p=a.position;p.y+=d.y*distance/steps;
        if(free(p)){if(p.y!=a.position.y)++movements;a.position.y=p.y;}else ++collisionBlocks;
    }
}
bool Game::fire(int index) {
    auto& a=actors.at(index);
    if(!a.alive||winner!=-1||a.cooldown>0||a.reloadTime>0||a.ammo<=0)return false;
    --a.ammo;++shots;a.cooldown=1/weapon.fireRate;
    // Deterministic spread keeps tests reproducible. First shot is centered.
    float angle=a.angle+(shots==1?0:std::sin(float(shots)*2.399f)*weapon.spread);
    int target=-1;float nearest=100;
    for(int i=0;i<int(actors.size());++i) {
        auto& b=actors[i];if(!b.alive||b.team==a.team)continue;
        Vec d=b.position-a.position;float forward=d.x*std::cos(angle)+d.y*std::sin(angle);
        float lateral=std::abs(d.x*std::sin(angle)-d.y*std::cos(angle));
        if(forward>0&&forward<nearest&&lateral<.28f&&map.visible(a.position,b.position)){target=i;nearest=forward;}
    }
    if(target>=0) {
        auto& b=actors[target];float absorbed=std::min(b.armor,weapon.damage*.4f);b.armor-=absorbed;b.health-=weapon.damage-absorbed;++hits;
        if(b.health<=0){b.health=0;b.alive=false;++a.kills;}
    }
    return true;
}
void Game::reload(int index) {
    auto& a=actors.at(index);if(a.alive&&a.reloadTime<=0&&a.ammo<weapon.magazine&&a.reserve>0)a.reloadTime=weapon.reloadDuration;
}
void Game::interact(int index,float dt) {
    auto& a=actors.at(index);if(!a.alive||winner!=-1)return;
    if((a.position-map.zone).length()>1.2f){a.interaction=0;return;}
    if(a.team==0&&index==carrier&&!planted) {
        a.interaction+=dt;if(a.interaction>=3){planted=true;bombTime=20;a.interaction=0;++plants;}
    } else if(a.team==1&&planted) {
        a.interaction+=dt;if(a.interaction>=5){++defuses;win(1);}
    }
}
void Game::bot(int index,float dt) {
    auto& a=actors[index];if(!a.alive)return;++botUpdates;
    int nearest=-1;float distance=1e9;
    for(int i=0;i<int(actors.size());++i) {
        auto& b=actors[i];float d=(b.position-a.position).length();
        if(b.alive&&b.team!=a.team&&d<distance&&map.visible(a.position,b.position)){nearest=i;distance=d;}
    }
    Vec goal=map.zone;
    if(nearest>=0) {
        Vec delta=actors[nearest].position-a.position;a.angle=std::atan2(delta.y,delta.x);
        if(a.ammo==0)reload(index);else fire(index);
        if(distance<4&&!planted&&index!=carrier)return;
    }
    if((a.position-map.zone).length()<1.1f&&((index==carrier&&!planted)||(a.team==1&&planted))) {
        interact(index,dt);return;
    }
    if(a.team==1&&!planted)goal=map.spawns[0][index%3];
    if(a.team==0&&planted)goal=map.spawns[1][index%3];
    Vec waypoint=map.nextStep(a.position,goal),d=waypoint-a.position;
    if(d.length()>.1f) {
        if(nearest<0)a.angle=std::atan2(d.y,d.x);
        move(a,d*(1/d.length()),dt);
    }
}
void Game::update(float dt,bool autonomousPlayer) {
    if(!std::isfinite(dt)||dt<=0)return;
    if(winner!=-1){roundDelay-=dt;if(roundDelay<=0)newRound();return;}
    for(auto& a:actors) {
        a.cooldown=std::max(0.f,a.cooldown-dt);
        if(a.reloadTime>0) {
            a.reloadTime-=dt;if(a.reloadTime<=0){int amount=std::min(weapon.magazine-a.ammo,a.reserve);a.ammo+=amount;a.reserve-=amount;}
        }
    }
    if(!actors[carrier].alive&&!planted) for(int i=0;i<3;++i)if(actors[i].alive){carrier=i;break;}
    for(int i=autonomousPlayer?0:1;i<int(actors.size());++i)bot(i,std::min(dt,.1f));
    remaining-=dt;
    if(planted){bombTime-=dt;if(bombTime<=0)win(0);} else if(remaining<=0)win(1);
    int alive[2]={0,0};for(auto& a:actors)if(a.alive)++alive[a.team];
    if(!alive[1])win(0);else if(!alive[0]&&!planted)win(1);
}
}
