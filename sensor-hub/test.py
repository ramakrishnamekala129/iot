import os
import json
import unittest
import datetime as dt
import csv

from sqlalchemy import desc

import sensor_hub
import analytics

from models import Record
from sensor_hub import app, db_session


class HubTest(unittest.TestCase):

    def setUp(self):
        sensor_hub.setup('test')
        self.app = app.test_client()

    def tearDown(self):
        sensor_hub.interrupt()
        db_session.close()
        os.remove('/tmp/test.db')

    def test_create_record(self):
        record = Record(7, 256, 1464191598)
        db_session.add(record)
        db_session.commit()
        records = Record.query.all()
        assert len(records) == 1
        self.assertEqual(records[0].timestamp, 1464191598)
        self.assertEqual(records[0].pin_num, 7)
        self.assertEqual(records[0].value, 768)

    def test_single_message_single_sensor(self):
        res = self.app.post('/api/records', data='1464191598,7:1024')
        assert res.status_code == 200
        records = Record.query.all()
        assert len(records) == 1
        self.assertEqual(records[0].timestamp, 1464191598)
        self.assertEqual(records[0].pin_num, 7)
        self.assertEqual(records[0].value, 0)

    def test_single_message_multiple_sensors(self):
        res = self.app.post('/api/records', data='1464191598,7:1024,8:768')
        assert res.status_code == 200
        records = Record.query.all()
        assert len(records) == 2
        self.assertEqual(records[0].timestamp, 1464191598)
        self.assertEqual(records[0].pin_num, 7)
        self.assertEqual(records[0].value, 0)
        self.assertEqual(records[1].timestamp, 1464191598)
        self.assertEqual(records[1].pin_num, 8)
        self.assertEqual(records[1].value, 256)

    def test_single_message_with_multiple_kinds_of_sensors(self):
        res = self.app.post(
            '/api/records', data='1475429113,a_uuid,dht11_5:21;42,hygro_0:856,'
            'hygro_1:1023,hygro_2:525,hygro_3:538,photocell_7:42')
        assert res.status_code == 200
        records = Record.query.all()
        assert len(records) == 2
        self.assertEqual(records[0].timestamp, 1464191598)
        self.assertEqual(records[0].pin_num, 7)
        self.assertEqual(records[0].value, 1024)
        self.assertEqual(records[1].timestamp, 1464191598)
        self.assertEqual(records[1].pin_num, 8)
        self.assertEqual(records[1].value, 768)

    def test_multiple_messages(self):
        data = ('1464181598,7:1024\n'
                '1464191598,6:768,9:512')
        res = self.app.post('/api/records', data=data)
        assert res.status_code == 200
        records = Record.query.all()
        assert len(records) == 3

    def test_not_good(self):
        data = ('1024')
        res = self.app.post('/api/records', data=data)
        assert res.status_code == 400
        records = Record.query.all()
        assert len(records) == 0

    def test_get_latest(self):
        db_session.add(Record(1, 1024, 1464191598))
        db_session.add(Record(2, 1023, 1464191598))
        db_session.add(Record(3, 1022, 1464191598))

        db_session.add(Record(1, 1021, 1564191598))
        db_session.add(Record(2, 1020, 1564191598))

        db_session.add(Record(1, 1, 1364191598))
        db_session.add(Record(2, 2, 1364191598))
        db_session.add(Record(3, 3, 1364191598))

        db_session.commit()

        res = self.app.get('/api/records/latest')
        assert res.status_code == 200
        records = json.loads(res.data.decode('utf8'))
        print(records)
        assert 'latest' in records
        assert 'soil_humidity' in records['latest']
        records = records['latest']['soil_humidity']
        self.assertEqual(3, len(records))

        self.assertEqual(records[0]['pin_num'], 1)
        self.assertEqual(records[0]['timestamp'], 1564191598)
        self.assertEqual(records[0]['value'], 3)

        self.assertEqual(records[1]['pin_num'], 2)
        self.assertEqual(records[1]['timestamp'], 1564191598)
        self.assertEqual(records[1]['value'], 4)

        self.assertEqual(records[2]['pin_num'], 3)
        self.assertEqual(records[2]['timestamp'], 1464191598)
        self.assertEqual(records[2]['value'], 2)

    def test_get_history(self):
        db_session.add(Record(1, 100, 1468588400))

        db_session.add(Record(1, 1024, 1468939853))
        db_session.add(Record(2, 1023, 1468939853))
        db_session.add(Record(3, 1022, 1468939853))

        db_session.add(Record(1, 1021, 1468853452))
        db_session.add(Record(2, 1020, 1468853452))
        db_session.add(Record(3, 1020, 1468853452))

        db_session.add(Record(1, 1, 1468883452))
        db_session.add(Record(2, 2, 1468883452))
        db_session.add(Record(3, 3, 1468883452))

        db_session.commit()

        res = self.app.get('/api/records/1468688400')
        assert res.status_code == 200
        history = json.loads(res.data.decode('utf8'))
        assert 'history' in history
        history = history['history']
        self.assertEqual(3, len(history['soil_humidity']))

        self.assertEqual(3, len(history['soil_humidity']['1']))
        self.assertEqual(history['soil_humidity']['1'][0]['x'], 1468939853)
        self.assertEqual(history['soil_humidity']['1'][0]['y'], 0)
        self.assertEqual(history['soil_humidity']['1'][1]['x'], 1468853452)
        self.assertEqual(history['soil_humidity']['1'][1]['y'], 3)
        self.assertEqual(history['soil_humidity']['1'][2]['x'], 1468883452)
        self.assertEqual(history['soil_humidity']['1'][2]['y'], 1023)

        self.assertEqual(3, len(history['soil_humidity']['2']))
        self.assertEqual(history['soil_humidity']['2'][0]['x'], 1468939853)
        self.assertEqual(history['soil_humidity']['2'][0]['y'], 1)
        self.assertEqual(history['soil_humidity']['2'][1]['x'], 1468853452)
        self.assertEqual(history['soil_humidity']['2'][1]['y'], 4)
        self.assertEqual(history['soil_humidity']['2'][2]['x'], 1468883452)
        self.assertEqual(history['soil_humidity']['2'][2]['y'], 1022)

        self.assertEqual(3, len(history['soil_humidity']['3']))
        self.assertEqual(history['soil_humidity']['3'][0]['x'], 1468939853)
        self.assertEqual(history['soil_humidity']['3'][0]['y'], 2)
        self.assertEqual(history['soil_humidity']['3'][1]['x'], 1468853452)
        self.assertEqual(history['soil_humidity']['3'][1]['y'], 4)
        self.assertEqual(history['soil_humidity']['3'][2]['x'], 1468883452)
        self.assertEqual(history['soil_humidity']['3'][2]['y'], 1021)


class AnalyticsTest(unittest.TestCase):

    def setUp(self):
        self.now = mock_datetime(2016, 7, 18, 16, 25)
        app = sensor_hub.setup('test')
        self.app = app.test_client()

    def tearDown(self):
        sensor_hub.interrupt()
        db_session.close()
        os.remove('/tmp/test.db')

    def gen_data(self, offset=None):
        self.all_records = []
        with open('fixtures/rel_humidity_data_short.csv') as csvfile:
            reader = csv.reader(csvfile)

            for i, row in enumerate(reader):
                record = Record(row[1], int(row[2]), row[0])
                self.all_records.append(record)

                if not offset or i >= offset:
                    db_session.add(record)

            db_session.commit()
            db_session.close()

    def test_get_last_watering_timestamp(self):
        with self.now:
            self.gen_data()
            self.assertEqual(len(self.all_records), 31)
            actual = analytics._get_last_watering_timestamp(1)
            self.assertEqual(1468810074, actual)

    def test_predictions(self):
        with self.now:
            self.gen_data(offset=10)

            records = Record.query.filter(Record.pin_num == 1) \
                .order_by(desc(Record.timestamp)).all()
            self.assertEqual(21, len(records))
            poly = analytics._get_polynomial(1, 1468810074)

            for r in self.all_records[:-2]:
                prediction = analytics._predict_at(
                    float(r.timestamp), poly, 1468810074)
                # err = prediction - float(r.value)
                # print(prediction, r.value, err)

                # Test prediction is ~20% accurate
                self.assertFalse(prediction > float(r.value) * 1.2)
                self.assertFalse(prediction < float(r.value) * 0.8)
                # print(prediction, r.value)

            self.assertEqual(analytics._predict_next_watering(
                poly, 1468810074), 1468810074 + 108000)


class mock_datetime(object):
    """
    Monkey-patch datetime for predictable results.
    From https://github.com/dbader/schedule/blob/master/test_schedule.py
    """
    def __init__(self, year, month, day, hour, minute):
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute

    def __enter__(self):
        class MockDate(dt.datetime):
            @classmethod
            def today(cls):
                return cls(self.year, self.month, self.day)

            @classmethod
            def now(cls):
                return cls(self.year, self.month, self.day,
                           self.hour, self.minute)
        self.original_datetime = dt.datetime
        dt.datetime = MockDate

    def __exit__(self, *args, **kwargs):
        dt.datetime = self.original_datetime


if __name__ == '__main__':
    unittest.main()
