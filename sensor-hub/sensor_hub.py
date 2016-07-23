#!/usr/bin/env python3
import sys
import datetime as dt

from flask import Flask, request, jsonify
from sqlalchemy import Column, Integer, func, desc, between
from sqlalchemy.ext.declarative import declarative_base
from numpy.polynomial import polynomial

from database import db_session, init_db, init_engine

app = Flask(__name__)

Base = declarative_base()


class Record(Base):
    __tablename__ = 'records'
    query = db_session.query_property()

    id = Column(Integer, primary_key=True)
    timestamp = Column(Integer)
    pin_num = Column(Integer)
    value = Column(Integer)

    def __init__(self, pin_num, value, timestamp=None):
        self.timestamp = timestamp
        self.value = value
        self.pin_num = pin_num

    def as_pub_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'pin_num': self.pin_num,
            'value': self.value
        }


def __bad_request():
    return 'not good', 400


def __to_pub_list(elements):
    return list(map(lambda e: e.as_pub_dict(), elements))


@app.route('/api/records/latest', methods=['GET'])
def get_lastest_records():
    records = Record.query.group_by(Record.pin_num) \
        .having(func.max(Record.timestamp)).all()

    return jsonify({'records': __to_pub_list(records)}), 200


@app.route('/api/records/<since_epoch_sec>', methods=['GET'])
def get_records_history(since_epoch_sec):
    history = {}
    records = Record.query.filter(Record.timestamp >= since_epoch_sec).all()

    for r in records:
        if r.pin_num not in history:
            history[r.pin_num] = []

        history[r.pin_num].append({'x': r.timestamp, 'y': r.value})
    return jsonify({'history': history}), 200


@app.route('/api/records', methods=['POST'])
def add_record():
    try:
        for timestamp_line in request.data.decode('utf-8').split('\n'):
            pieces = timestamp_line.split(',')
            if len(pieces) < 2:
                return __bad_request()

            timestamp = pieces[0]
            for piece in pieces[1:]:
                db_session.add(Record(*(piece).split(':'), timestamp=timestamp))
                db_session.commit()

        return 'ok', 200
    except Exception:
        return __bad_request()


def _get_last_watering_timestamp(pin_num):
    records = Record.query.filter(Record.pin_num == pin_num) \
        .order_by(desc(Record.timestamp)).limit(500).all()
    watering_thresold = 100  # Minimum fluctuation to consider a watering
    last_record = records[0]

    for current in records[1:]:

        if current.value > last_record.value \
         and current.value - last_record.value > watering_thresold:
            return last_record.timestamp
        last_record = current


def _get_polynomial(pin_num, start, stop=dt.datetime.now()):
    records = Record.query \
        .filter(Record.pin_num == pin_num) \
        .filter(between(Record.timestamp, start, stop)) \
        .order_by(Record.timestamp).all()
    x = []
    y = []
    for r in records:
        x.append((r.timestamp - start))
        y.append(int(r.value))
    return polynomial.polyfit(x, y, 1)


def _predict(pin_num, at_time, polynom):
    last_watering = _get_last_watering_timestamp(pin_num)
    return polynomial.polyval((at_time - last_watering), polynom)


def setup(env=None):
    app.config.from_pyfile('config/default.py')
    app.config.from_pyfile('config/%s.py' % env, silent=True)

    init_engine(app.config['DATABASE_URI'])
    init_db(Base)
    return app

if __name__ == '__main__':
    setup(sys.argv[1] if len(sys.argv) > 1 else None).run()
