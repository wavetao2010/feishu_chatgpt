from sqlalchemy import Column, Integer, String,DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class MessageHistory (Base):
    __tablename__ = 'MessageHistory'
    EMP_ID = Column(Integer, primary_key=True)
    open_id = Column(String(250), nullable=False)
    role = Column(String(250), nullable=False)
    message = Column(String(250), nullable=False)
    message_time = Column(Integer, nullable=False)
