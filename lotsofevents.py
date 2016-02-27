from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import User, Organizer, Event, Base
from datetime import datetime, date, time

engine = create_engine('sqlite:///events.db')
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. Any change made against the objects in the
# session won't be persisted into the database until you call
# session.commit(). If you're not happy about the changes, you can
# revert all of them back to the last commit by calling
# session.rollback()
session = DBSession()


# Create dummy user
User1 = User(name="Mohammed Safwat", email="mail.msafwat@gmail.com",
             picture='https://pbs.twimg.com/profile_images/519046593937281024/KLDpy046_400x400.png')
session.add(User1)
session.commit()

organizer1 = Organizer(user_id=1, name="Virgin Megastore", organizer_thumbnail_url="http://the3doodler.com/wp-content/uploads/2015/02/virgin_megastore.jpg")

session.add(organizer1)
session.commit()

event1 = Event(user_id=1, name="RedFest DXB", event_url="http://tickets.virginmegastore.me/?event_id=3494",
               event_thumbnail_url="", description="VirignMegastore RedFest", ticket_price="$7.50",
               start_date=datetime.now(), featured=True)

session.add(event1)
session.commit()

print "added events!"
