#pragma once
#include <cmath>
#include <string>
#include <vector>

namespace bo2cs {
struct Vec {
    float x=0,y=0;
    Vec operator+(Vec b) const { return {x+b.x,y+b.y}; }
    Vec operator-(Vec b) const { return {x-b.x,y-b.y}; }
    Vec operator*(float k) const { return {x*k,y*k}; }
    float length() const { return std::sqrt(x*x+y*y); }
};
struct Map {
    std::vector<std::string> rows;
    std::vector<Vec> spawns[2];
    Vec zone;
    float scale=1;
    bool walkable(float x,float y) const;
    bool visible(Vec a,Vec b) const;
    Vec nextStep(Vec from,Vec destination) const;
};
struct Weapon {
    float damage=24, fireRate=6, reloadDuration=1.7f, spread=.035f, recoil=.012f;
    int magazine=24,reserve=144;
};
struct Actor {
    Vec position;
    float angle=0,health=100,armor=50,cooldown=0,reloadTime=0,interaction=0;
    int team=0,ammo=24,reserve=144,kills=0;
    bool alive=true;
};
class Game {
public:
    Map map;
    Weapon weapon;
    std::vector<Actor> actors;
    float remaining=90,bombTime=20,roundDelay=0;
    int scores[2]={0,0},winner=-1,carrier=0,round=0;
    bool planted=false;
    unsigned long shots=0,hits=0,botUpdates=0,movements=0,collisionBlocks=0,plants=0,defuses=0;
    void load(const std::string& mapFile,const std::string& weaponsFile);
    void newRound();
    void win(int team);
    void move(Actor& actor,Vec direction,float dt);
    bool fire(int index);
    void reload(int index);
    void interact(int index,float dt);
    void update(float dt,bool autonomousPlayer=false);
private:
    void bot(int index,float dt);
};
}
