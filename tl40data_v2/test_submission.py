#! /usr/bin/env python3

# 3-1-2023: This can successfully add a Response to the db. It also
# demonstrates that creation of the trainer works if the trainer didn't exist.


from argparse import ArgumentParser
from tables import Stat, Trainer, Response

# Third party
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine, event
from sqlalchemy.engine import ExceptionContext

# Local
from settings import LOCAL_DB_SPECIFIER, LOCAL_DB_FILENAME


sub = \
[('trainername', 'prometheus'),
('total_xp', ''),
# ('trainer', ''),  # not sure where I got this line from
('trainer_level', ''),
('pokedex_caught', ''),
('pokedex_seen', ''),
('pokedex_entries_unknown', ''),
# Left out: the special dexes
('pokemon_info_stardust', ''),
('go_battle_league_overall_wins', ''),
('go_battle_league_overall_played', ''),
('go_battle_league_overall_streak', ''),
('elite_collector_challenge', ''),
('gymbadges_total', ''),
('gymbadges_gold', '2'),
('travel_km', '2'),
('pokedex_entries', '2'),
('capture_total', '2'),
('evolved_total', ''),
('hatched_total', ''),
('pokestops_visited', ''),
('pokestops_visited_unique', ''),
('big_magikarp', ''),
('battle_attack_won', ''),
('battle_training_won', ''),
('small_rattata', ''),
('pikachu', ''),
('unown', ''),
('pokedex_entries_gen2', ''),
('raid_battle_won', ''),
('legendary_battle_won', ''),
('berries_fed', ''),
('hours_defended', ''),
('pokedex_entries_gen3', ''),
('challenge_quests', ''),
('max_level_friends', ''),
('trading', ''),
('trading_distance', ''),
('pokedex_entries_gen4', ''),
('great_league', ''),
('ultra_league', ''),
('master_league', ''),
('photobomb', ''),
('pokedex_entries_gen5', ''),
('purifier', ''),
('hero', ''),
('ultra_hero', ''),
('best_buddy', ''),
('wayfarer_agreements', ''),
('pokedex_entries_gen6', ''),
('pokedex_entries_gen7', ''),
('pokedex_entries_gen8', ''),
('pokedex_entries_gen9', ''),
('pokestreak', ''),
('raid_battle_unique', ''),
('raid_battle_friends', ''),
('lure_module_catches', ''),
('mega_evolves', ''),
('pokedex_entries_mega_dex', ''),
('referral', ''),
('raid_expert', ''),
('tinycollector', ''),
('jumbocollector', ''),
('vivilloncollector', ''),
('type_normal', ''),
('type_fighting', ''),
('type_flying', ''),
('type_poison', ''),
('type_ground', ''),
('type_rock', ''),
('type_bug', ''),
('type_ghost', ''),
('type_steel', ''),
('type_fire', ''),
('type_water', ''),
('type_grass', ''),
('type_electric', ''),
('type_psychic', ''),
('type_ice', ''),
('type_dragon', ''),
('type_dark', ''),
('type_fairy', '')]




def main():
    """ Get command line args, and call the function that fill the static tables.
    """
    parser = ArgumentParser("Fill in non-user-submitted data to a db")
    args = parser.parse_args()

    db_specifier = LOCAL_DB_SPECIFIER 
    #engine = get_engine(db_specifier)
    engine = create_engine(db_specifier)
    session = Session(engine, autoflush=True)

    # Do stuff

    #sub_as_dict = dict(sub)

    #sub_as_dict["trainer"] = sub_as_dict.pop("trainername")
    #response = Response(**sub_as_dict)

    response = Response.save_response(session, response_values=dict(sub))

    session.commit()
    session.flush()
    session.close()


if __name__ == '__main__':
    main()
