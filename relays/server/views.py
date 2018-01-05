from flask import Blueprint, jsonify, request, send_from_directory

from server import db
from server.models import Pin


relays_blueprint = Blueprint('relays', __name__,)
static_blueprint = Blueprint('static', __name__,)


def __to_pub_list(elements):
    return list(map(lambda e: e.as_pub_dict(), elements))


@relays_blueprint.route('/api/relays', methods=['GET'])
def get_relays():
    return jsonify({'relays': __to_pub_list(Pin.query.all())}), 200


@relays_blueprint.route('/api/relays/<pin_id>', methods=['POST'])
def put_relays(pin_id):
    data = request.get_json()
    wanted_state = data.get('state_str')
    reset_to_auto = wanted_state == 'auto'

    # p = synced_pins[int(pin_id)]
    p = Pin.query.filter(Pin.pin_id == int(pin_id)).one()

    if reset_to_auto:
        p.reset_user_override()
    else:
        p.set_user_override(wanted_state)
    db.session.add(p)

    p = Pin.query.filter(Pin.pin_id is int(pin_id)).one()
    # Share to other processes
    return jsonify({'relay': p.as_pub_dict()}), 200


@static_blueprint.route('/')
def index():
    return send_from_directory('public', 'index.html')


@static_blueprint.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)
