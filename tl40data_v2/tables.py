#! /usr/bin/env python3

# Standard library
from argparse import ArgumentParser
import datetime
import os

# Third party
import sqlalchemy
from sqlalchemy import (Boolean, Column, DateTime, ForeignKey,
                        select, Integer, PickleType, String)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import registry, declarative_base, relationship, Session
from sqlalchemy import create_engine, event
from sqlalchemy.orm.exc import NoResultFound, UnmappedInstanceError
import sqlite3

# Local
from settings import LOCAL_DB_SPECIFIER 


Base = declarative_base()

#class Responses_and_Trainers(Base):
#    __tablename__ = 'responses_and_trainers'
#    ## Schema
#    id = Column(Integer, primary_key=True)
#    trainer_id = Column(Integer, ForeignKey('trainer.id'))
#    responses = relationship("Response", back_populates="trainer")
#
#    # One to many table of responses for a trainer




class Stat(Base):
    __tablename__ = 'stat'
    ## Schema
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    short_name = Column(String, unique=True)  # or make this the primary key?
    icon = Column(String)
    numtype = Column(String)
    bronze = Column(Integer)
    silver = Column(Integer)
    gold = Column(Integer)
    platinum = Column(Integer)
    maximum = Column(Integer)
    required = Column(Boolean)
    monotonic = Column(Boolean)  # TODO nullable? what has been stored to-date?
    order_idx = Column(Integer)  # dictates order aka position in response.strdata

    def __init__(self, *args, **kwargs):
        #print("OHHH")
        #print(kwargs)
        super().__init__(*args, **kwargs)
        if "icon" in kwargs:
            self.icon
        #print(self.icon)

    @classmethod
    def get_all_names(cls, session):
        """Get all stat names in DB order, like ['Total XP', 'Trainer Level', ...]

        Returns:
            List of stat names
        """
        # For now, this order_by ought to be a no-op.
        # But if we were to do something funky with an existing stat, or add a new stat
        # not to the end...
        # TODO confirm this is a list of strings
        #return session.Select(Stat.name).order_by(Stat.order_idx)
        return session.query(Stat.name).order_by(Stat.order_idx).all()

    @classmethod
    def unpack_strdata(cls, strdata, session, keys=None, pad_data=False):
        """Given a Response.strdata string, return a dictionary of stat names and values


        """
        # 
        names = cls.get_all_names(session)
        names = [name[0] for name in names]
        # strdata is inserted in db-correct order, so we know the order after splitting.
        strdata_vals = strdata.split(";")
        # This assertion would point at a database mismatch, maybe.
        if pad_data:
            if zeros_to_append := len(names) - len(strdata_vals):
                strdata_vals += ["0"] * zeros_to_append
        else:
            assert len(strdata_vals) == len(names)
        ## TODO are names pretty or icon names? Answer: pretty
        #return dict(zip(names, strdata_vals))
        #return {name: {"value": int(val) if val else 0} for name, val in zip(names, strdata_vals)}
        retdict = {}
        for name, val in zip(names, strdata_vals):
            if name not in retdict:
                retdict[name] = {}
            if val:
                try:
                    retdict[name]["value"] = int(val)
                except ValueError:
                    retdict[name]["value"] = float(val)
            else:
                retdict[name]["value"] = 0
        return retdict



class Trainer(Base):
    __tablename__ = 'trainer'

    ## Schema
    id = Column(Integer, primary_key=True)
    name = Column(String)#, unique=True)
    proper_name = Column(String)#, unique=True)
    start_date = Column(String, nullable=True)
    # 2-26: implementing One to Many, bidirectionally
    responses = relationship("Response", back_populates="trainer")  # Unsure about the back_populates; came from copilot
    # This buggy line probably came from copilot
    #newest_response = Column("Response", ForeignKey('response.id'), nullable=True)
    #newest_response = Column(Response, nullable=True)  # Can't use a table class as a type
    newest_response = Column(Integer, nullable=True)
    newest_response_date = Column(String, nullable=True)  # Actually a timestamp... TODO refactor

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create_trainer(self, name):
        pass

    def get_newest_response(self, session):
        """Get a dictionary of latest response information for this trainer

        Returns:
            List of tuples of (key, value) for each stat in the response
        """
        # TODO Do we need to do a query here? Or can we just return the newest_response attribute
        if not self.newest_response:
            print(f"'newest_response' not set for {self.name}")
            return None

        # Get the Response object from the integer id self.newest_response
        response = session.query(Response).filter(Response.id == self.newest_response).one()
        response_values = response.strdata.split(";")
        response_dict = dict(zip(Stat.get_all_names(session), response_values))
        return response_dict


class Response(Base):
    __tablename__ = 'response'

    ## Schema
    id = Column(Integer, primary_key=True)
    timestamp= Column(String)  # timestamp, often converted to datetime or date object
    #trainer = Column(String)
    # What about bidirectional?
    trainer_id = Column(Integer, ForeignKey('trainer.id'))
    trainer = relationship("Trainer", back_populates="responses")  # copilot
    # TODO a column containing a list?
    #(list? with) values for every row in stat table
    # Since we're using sqlite3, which doesn't support ARRAY, encode our list of numbers as a comma delimited list.
    # The save result function will handle a list of tuples of (key,value) and put them in the
    # correct order (per the Stat table), and store the appropriate strdata=[value1,value2,...]
    strdata = Column(String)
    edited = Column(Integer, nullable=True)
    revision = Column(Integer, nullable=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def save_response(cls, session, response_values, timestamp=None):
        """Save a response to the database"""
        # TODO simple hack for now: we do a list comprehension below where we skip just the "trainername"
        # response_values is expected to be a:
        #   CombinedMultiDict(get, post)
        # where get and post are both werkzeug.datastructures.ImmutableMultiDict objects,
        # which can be interacted with as a single dictionaries (chained dictionaries...)
        # The order will be per stats.json.  This needs to be coerced into the order the
        # corresponding Stat rows exist in the DB.
        # The keys of response_values are the icon names, not the pretty names.

        # Stats list from DB
        #stat_data = session.query(Stat).all().order_by(Stat.order_idx)
        stat_data = session.query(Stat.icon).order_by(Stat.order_idx).all()  # list of tuples
        #stats_order_lookup = {stat.icon: stat.order_idx for stat in stat_data}
        #stat_data_dict = {stat.icon: 0 for stat in stat_data}
        stat_data_dict = {icon[0]: 0 for icon in stat_data}

        # Put response values in DB's order of Stats
        #key_val_order = [(k, v, stats_order_lookup[k]) for k, v in response_values.items() if k != "trainername"]
        #key_val_order.sort(key=lambda x: x[2])
        #print(stat_data_dict)
        #print(len(stat_data_dict))
        #print(list(response_values.keys()))
        #print(len(list(response_values.keys())))
        for k, v in response_values.items():
            # Presently, everything but the trainername is a numeric survey value
            if k == "trainername":
                continue
            stat_data_dict[k] = v
        # Then make the values a single string
        # The values are in order of the order in the DB (NOT the orderidx column though)
        #strdata = ";".join([v for k, v, o in key_val_order])
        strdata = ";".join(str(val) for val in stat_data_dict.values())

        # Response DB object
        if not timestamp:
            timestamp = str(datetime.datetime.now().timestamp())
        trainer_proper_name = response_values["trainername"]
        trainer = trainer_proper_name.lower()
        trainer_obj = session.query(Trainer).filter(Trainer.name == trainer).first()
        if trainer_obj is None:
            trainer_obj = Trainer(name=trainer, proper_name=trainer_proper_name, start_date=timestamp)
            session.add(trainer_obj)
            session.flush()  # copilot
            session.commit()  # copilot
        response = cls(trainer_id=trainer_obj.id, timestamp=timestamp, strdata=strdata, revision=1)
        print(trainer_obj)

        # Add response object, so we can get the id
        session.add(response)

        # Set trainer's newest_response, and use whichever name capitalization they gave this time
        print("existing newest response date:", trainer_obj.newest_response_date)
        print("Do timestamp types match?:", type(timestamp), type(trainer_obj.newest_response_date))
        print("  and is it equivalen to None in python?", trainer_obj.newest_response_date is None)
        if trainer_obj.newest_response_date is None or timestamp > trainer_obj.newest_response_date:
            trainer_obj.newest_response_date = timestamp
            trainer_obj.newest_response = response.id
        trainer_obj.proper_name = trainer_proper_name

        session.add(trainer_obj)
        session.flush()
        session.commit()

        return response

    def list_responses(cls, session, trainername):
        # TODO
        pass


#def create_tables(engine: sqlalchemy.future.engine.Engine = None):
#    """ Creates the tables in the specified database.
#
#    Args:
#        engine: SQLAlchemy engine
#    """
#    Base.metadata.create_all(engine)
#    session = Session(engine)
#    session.commit()
#    session.close()


def main():
    """ Get command line args, and call the function that fill the static tables.
    """
    parser = ArgumentParser("Fill in non-user-submitted data to a db")
    args = parser.parse_args()

    db_specifier = LOCAL_DB_SPECIFIER 
    #engine = get_engine(db_specifier)
    engine = create_engine(db_specifier)

    # Create the tables
    Base.metadata.create_all(engine)

    # alembic... see if this stamps some sort of version on a fresh table
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config("alembic.ini")
    command.stamp(alembic_cfg, "head")

    session = Session(engine, autoflush=True)
    session.commit()
    session.flush()
    session.close()


if __name__ == '__main__':
    main()
