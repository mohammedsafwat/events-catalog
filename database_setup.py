from sqlalchemy import Column, ForeignKey, Integer, String, Date, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()

class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key = True)
    name = Column(String(250), nullable = False)
    email = Column(String(250), nullable = False)
    picture = Column(String(250))

class Organizer(Base):
    __tablename__ = 'organizer'

    id = Column(Integer, primary_key = True)
    name = Column(String(250), nullable = False)
    organizer_thumbnail_url = Column(String(250))
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)
    events = relationship("Event", cascade='all, delete-orphan')
    
    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'name'           : self.name,
            'id'             : self.id,
            'thumbnail_url'  : self.organizer_thumbnail_url
        }

class Event(Base):
    __tablename__ = 'event'

    id = Column(Integer, primary_key = True)
    name = Column(String(80), nullable = False)
    description = Column(String(250))
    event_url = Column(String(255))
    event_thumbnail_url = Column(String(255))
    ticket_price = Column(String(8))
    start_date = Column(Date)
    featured = Column(Boolean, default=False)
    organizer_id = Column(Integer,ForeignKey('organizer.id'))
    organizer = relationship(Organizer)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'id'                    : self.id,
            'name'                  : self.name,
            'event_url'             : self.event_url,
            'event_thumbnail_url'   : self.event_thumbnail_url,
            'description'           : self.description,
            'ticket_price'          : self.ticket_price,
            'start_date'            : str(self.start_date),
            'featued'               : self.featured
       }

engine = create_engine('sqlite:///events.db')

Base.metadata.create_all(engine)
