#include "Game.hpp"
#include <iostream>
#include <stdexcept>

using namespace bo2cs;
void check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
int main(int argc, char** argv) {
    try {
        Game game;
        game.load(argv[1], argv[2]);
        check(game.actors.size() >= 5, "player plus four bots must spawn");
        check(!game.map.walkable(-1, -1), "outside map blocks movement");
        auto& player = game.actors[0];
        player.position = {1.3f, 1.3f};
        game.move(player, {-1, 0}, 1);
        check(player.position.x >= 1.2f, "movement must not tunnel through boundary");
        player.position = {2.5f,2.5f}; player.angle = 0;
        auto& enemy = game.actors[3];
        enemy.position = {4.5f,2.5f};
        const float initial = enemy.health;
        check(game.fire(0), "loaded weapon must fire");
        check(enemy.health < initial, "hitscan must damage visible enemy");
        check(!game.fire(0), "cooldown prevents immediate duplicate shot");
        player.ammo = 0; game.reload(0);
        game.update(game.weapon.reloadDuration + .1f, false);
        check(player.ammo == game.weapon.magazine, "reload transfers reserve into magazine");
        player.position = {3.5f, 3.5f}; enemy.position = {6.5f,3.5f}; player.angle = 0; player.cooldown = 0;
        const float blocked = enemy.health;
        game.fire(0);
        check(enemy.health == blocked, "wall must block hitscan damage");
        game.newRound();
        game.actors[0].position = game.map.zone;
        for (int i=0;i<40;++i) game.interact(0,.1f);
        check(game.planted, "carrier must plant after sustained interaction");
        game.actors[3].position = game.map.zone;
        for (int i=0;i<60;++i) game.interact(3,.1f);
        check(game.winner == 1, "defuse must give defense round win");
        game.newRound();
        game.remaining = .1f; game.update(.2f, false);
        check(game.winner == 1, "round timeout must give defense victory");
        game.newRound();
        auto before = game.botUpdates;
        for (int i=0;i<600;++i) game.update(1.f/60, true);
        check(game.botUpdates > before + 1000, "bots must update autonomously");
        check(game.shots > 2, "autonomous bots must fire weapons");
        std::cout << "PASS: movement, collision, hitscan, reload, objective, rounds, bots\n";
        return 0;
    } catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
