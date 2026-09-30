from datetime import datetime
from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Rate per hour in Indian Rupees (₹)
HOURLY_RATE = 50.00


class User(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(50), unique=True, nullable=False)
  password = db.Column(db.String(50), nullable=False)


class ParkingSlot(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  slot_number = db.Column(db.String(10), unique=True, nullable=False)
  vehicle_number = db.Column(db.String(20), nullable=True)
  vehicle_type = db.Column(db.String(20), nullable=True)
  entry_time = db.Column(db.DateTime, nullable=True)
  status = db.Column(db.String(20), default='Available')


class ParkingHistory(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  vehicle_number = db.Column(db.String(20), nullable=False)
  vehicle_type = db.Column(db.String(20), nullable=False)
  slot_number = db.Column(db.String(10), nullable=False)
  entry_time = db.Column(db.String(30), nullable=False)
  exit_time = db.Column(db.String(30), nullable=False)
  duration_hours = db.Column(db.Float, nullable=False)
  fee = db.Column(db.Float, nullable=False)


with app.app_context():
  db.create_all()
  if ParkingSlot.query.count() == 0:
    for i in range(1, 21):
      db.session.add(ParkingSlot(slot_number=f'SLOT-{i:02d}'))
    db.session.commit()


@app.route('/')
def index():
  return render_template('index.html')


@app.route('/api/signup', methods=['POST'])
def signup():
  data = request.json
  username = data.get('username')
  password = data.get('password')
  if not username or not password:
    return jsonify({'error': 'Username and password required'}), 400
  if User.query.filter_by(username=username).first():
    return jsonify({'error': 'Username already exists!'}), 400
  db.session.add(User(username=username, password=password))
  db.session.commit()
  return jsonify({'message': 'Account created successfully! Please login.'})


@app.route('/api/login', methods=['POST'])
def login():
  data = request.json
  user = User.query.filter_by(
      username=data.get('username'), password=data.get('password')
  ).first()
  if user:
    return jsonify({'message': 'Login successful', 'username': user.username})
  return jsonify({'error': 'Invalid username or password'}), 401


@app.route('/api/slots', methods=['GET'])
def get_slots():
  slots = ParkingSlot.query.all()
  return jsonify([{
      'id': s.id,
      'slot_number': s.slot_number,
      'vehicle_number': s.vehicle_number,
      'vehicle_type': s.vehicle_type,
      'entry_time': s.entry_time.strftime('%Y-%m-%d %H:%M:%S')
      if s.entry_time
      else None,
      'status': s.status,
  } for s in slots])


@app.route('/api/park', methods=['POST'])
def park_vehicle():
  data = request.json
  slot_id = data.get('slot_id')
  vehicle_number = data.get('vehicle_number')
  vehicle_type = data.get('vehicle_type')

  if not slot_id or not vehicle_number or not vehicle_type:
    return (
        jsonify({'error': 'Slot, vehicle number and type are required'}),
        400,
    )

  slot = ParkingSlot.query.get_or_404(slot_id)
  if slot.status == 'Occupied':
    return jsonify({'error': 'Selected slot is already occupied!'}), 400

  existing = ParkingSlot.query.filter_by(
      vehicle_number=vehicle_number, status='Occupied'
  ).first()
  if existing:
    return (
        jsonify(
            {'error': f'Vehicle {vehicle_number} is already inside parked.'}
        ),
        400,
    )

  slot.vehicle_number = vehicle_number
  slot.vehicle_type = vehicle_type
  slot.entry_time = datetime.now()
  slot.status = 'Occupied'
  db.session.commit()

  return jsonify(
      {'message': f'Vehicle parked successfully in {slot.slot_number}'}
  )


@app.route('/api/exit/<int:slot_id>', methods=['POST'])
def vehicle_exit(slot_id):
  slot = ParkingSlot.query.get_or_404(slot_id)
  if slot.status == 'Available':
    return jsonify({'error': 'Slot is already empty'}), 400

  exit_time = datetime.now()
  duration_hours = (exit_time - slot.entry_time).total_seconds() / 3600.0
  charge = max(round(duration_hours * HOURLY_RATE, 2), HOURLY_RATE)

  db.session.add(
      ParkingHistory(
          vehicle_number=slot.vehicle_number,
          vehicle_type=slot.vehicle_type,
          slot_number=slot.slot_number,
          entry_time=slot.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
          exit_time=exit_time.strftime('%Y-%m-%d %H:%M:%S'),
          duration_hours=round(duration_hours, 2),
          fee=charge,
      )
  )

  v_num = slot.vehicle_number
  slot.vehicle_number = None
  slot.vehicle_type = None
  slot.entry_time = None
  slot.status = 'Available'
  db.session.commit()

  return jsonify({
      'message': f'Vehicle {v_num} checked out.',
      'duration_hours': round(duration_hours, 2),
      'fee': charge,
  })


@app.route('/api/history', methods=['GET'])
def get_history():
  history = ParkingHistory.query.order_by(ParkingHistory.id.desc()).all()
  total_revenue = sum([h.fee for h in history])
  history_list = [{
      'vehicle_number': h.vehicle_number,
      'vehicle_type': h.vehicle_type,
      'slot_number': h.slot_number,
      'entry_time': h.entry_time,
      'exit_time': h.exit_time,
      'duration_hours': h.duration_hours,
      'fee': h.fee,
  } for h in history]
  return jsonify({'history': history_list, 'total_revenue': total_revenue})


if __name__ == '__main__':
  app.run(debug=True)