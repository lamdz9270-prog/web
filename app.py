from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import os
import json
import hashlib
import uuid
import requests
from datetime import datetime

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
CORS(app, supports_credentials=True)

# ============ DATABASE ============
DATA_FILE = 'data.json'

def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {'users': [], 'products': [], 'orders': [], 'balances': {}, 'topups': [], 'news': []}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Tạo data.json nếu chưa có
if not os.path.exists(DATA_FILE):
    save_data({'users': [], 'products': [], 'orders': [], 'balances': {}, 'topups': [], 'news': []})

# ============ ADMIN AUTH ============
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'adminproxyvip')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'ndlxtp')
PARTNER_ID = os.environ.get('THE_SIEU_RE_PARTNER_ID', '')
PARTNER_KEY = os.environ.get('THE_SIEU_RE_PARTNER_KEY', '')

def require_admin():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    return None

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        return jsonify({'success': True, 'message': 'Đăng nhập thành công'})
    
    return jsonify({'success': False, 'message': 'Sai tài khoản hoặc mật khẩu'}), 401

@app.route('/api/admin/check-auth', methods=['GET'])
def admin_check_auth():
    if session.get('admin_logged_in'):
        return jsonify({'authenticated': True})
    return jsonify({'authenticated': False}), 401

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin_logged_in', None)
    return jsonify({'success': True})

# ============ ADMIN API ============
@app.route('/api/admin/orders', methods=['GET'])
def admin_orders():
    auth = require_admin()
    if auth: return auth
    db = load_data()
    return jsonify(db.get('orders', []))

@app.route('/api/admin/update-order', methods=['POST'])
def admin_update_order():
    auth = require_admin()
    if auth: return auth
    
    data = request.json
    order_id = data.get('id')
    delivery_data = data.get('deliveryData')
    auto_complete = data.get('autoComplete', False)
    
    db = load_data()
    for order in db['orders']:
        if order['id'] == order_id:
            order['deliveryData'] = delivery_data
            if auto_complete:
                order['status'] = 'Hoàn tất'
            save_data(db)
            return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Order not found'}), 404

@app.route('/api/admin/all-balances', methods=['GET'])
def admin_all_balances():
    auth = require_admin()
    if auth: return auth
    
    db = load_data()
    result = []
    for email, balance in db['balances'].items():
        result.append({'email': email, 'balance': balance})
    return jsonify(result)

@app.route('/api/admin/topup-list', methods=['GET'])
def admin_topup_list():
    auth = require_admin()
    if auth: return auth
    
    db = load_data()
    return jsonify(db.get('topups', []))

@app.route('/api/admin/adjust-balance', methods=['POST'])
def admin_adjust_balance():
    auth = require_admin()
    if auth: return auth
    
    data = request.json
    email = data.get('email')
    amount = int(data.get('amount', 0))
    reason = data.get('reason', '')
    
    db = load_data()
    old_balance = db['balances'].get(email, 0)
    db['balances'][email] = old_balance + amount
    save_data(db)
    
    return jsonify({'success': True, 'newBalance': db['balances'][email]})

@app.route('/api/admin/revenue', methods=['GET'])
def admin_revenue():
    auth = require_admin()
    if auth: return auth
    
    period = request.args.get('period', 'day')
    db = load_data()
    orders = db.get('orders', [])
    
    # Lọc đơn hàng đã thanh toán
    paid_orders = [o for o in orders if o.get('status') in ['PAID', 'Hoàn tất']]
    
    total = sum(o.get('total', 0) for o in paid_orders)
    count = len(paid_orders)
    avg = total // count if count > 0 else 0
    
    return jsonify({
        'success': True,
        'total': total,
        'count': count,
        'avg': avg,
        'details': [
            {'label': 'Hôm nay', 'total': total},
            {'label': 'Hôm qua', 'total': 0}
        ]
    })

@app.route('/api/admin/logs', methods=['GET'])
def admin_logs():
    auth = require_admin()
    if auth: return auth
    return jsonify([])

# ============ ADD PRODUCT ============
@app.route('/api/admin/add-product', methods=['POST'])
def add_product():
    auth = require_admin()
    if auth: return auth
    
    data = request.json
    db = load_data()
    
    new_product = {
        'id': str(uuid.uuid4()),
        'name': data.get('name'),
        'price': int(data.get('price', 0)),
        'catId': data.get('catId', ''),
        'image': data.get('image', ''),
        'desc': data.get('desc', ''),
        'isManual': int(data.get('isManual', 0)),
        'stock': data.get('stock', '')
    }
    db['products'].append(new_product)
    save_data(db)
    
    return jsonify({'success': True})

@app.route('/api/admin/delete-product', methods=['POST'])
def delete_product():
    auth = require_admin()
    if auth: return auth
    
    data = request.json
    product_id = data.get('id')
    db = load_data()
    
    db['products'] = [p for p in db['products'] if p['id'] != product_id]
    save_data(db)
    
    return jsonify({'success': True})

# ============ PRODUCTS ============
@app.route('/api/products', methods=['GET'])
def get_products():
    db = load_data()
    return jsonify(db.get('products', []))

# ============ AUTH ============
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('pass', '').strip()
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Vui lòng nhập đủ thông tin'}), 400
    
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Mật khẩu tối thiểu 6 ký tự'}), 400
    
    db = load_data()
    
    for user in db['users']:
        if user['email'] == email:
            return jsonify({'success': False, 'message': 'Email đã được đăng ký'}), 400
    
    new_user = {
        'id': str(uuid.uuid4()),
        'email': email,
        'password': hash_password(password),
        'display_name': email.split('@')[0],
        'created_at': datetime.now().isoformat()
    }
    db['users'].append(new_user)
    db['balances'][email] = 0
    save_data(db)
    
    return jsonify({'success': True, 'message': 'Đăng ký thành công!'})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('pass', '').strip()
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Nhập đầy đủ thông tin'}), 400
    
    db = load_data()
    
    for user in db['users']:
        if user['email'] == email and user['password'] == hash_password(password):
            session['user_email'] = email
            return jsonify({'success': True, 'message': 'Đăng nhập thành công'})
    
    return jsonify({'success': False, 'message': 'Sai email hoặc mật khẩu'}), 401

@app.route('/api/auth/me', methods=['GET'])
def get_me():
    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Unauthorized'}), 401
    
    db = load_data()
    for user in db['users']:
        if user['email'] == email:
            return jsonify({
                'email': email,
                'displayName': user.get('display_name', email.split('@')[0])
            })
    
    return jsonify({'error': 'User not found'}), 404

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.pop('user_email', None)
    return jsonify({'success': True})

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json
    email = data.get('email', '').strip().lower()
    
    db = load_data()
    for user in db['users']:
        if user['email'] == email:
            return jsonify({'success': True, 'message': 'Link đặt lại mật khẩu đã gửi đến email của bạn'})
    
    return jsonify({'success': False, 'message': 'Email không tồn tại'}), 404

# ============ BALANCE ============
@app.route('/api/balance', methods=['GET'])
def get_balance():
    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Unauthorized'}), 401
    
    db = load_data()
    balance = db['balances'].get(email, 0)
    return jsonify({'success': True, 'balance': balance})

# ============ ORDERS ============
@app.route('/api/create-order', methods=['POST'])
def create_order():
    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    cart = data.get('cart', [])
    payment_method = data.get('paymentMethod', 'balance')
    
    if not cart:
        return jsonify({'success': False, 'message': 'Giỏ hàng trống'}), 400
    
    total = sum(item['price'] * item['quantity'] for item in cart)
    
    db = load_data()
    balance = db['balances'].get(email, 0)
    
    order_id = str(int(datetime.now().timestamp()))
    
    if payment_method == 'balance':
        if balance < total:
            return jsonify({'success': False, 'message': 'Số dư không đủ'}), 400
        
        db['balances'][email] = balance - total
        
        new_order = {
            'id': order_id,
            'email': email,
            'total': total,
            'status': 'PAID',
            'deliveryData': 'Chờ admin xử lí đơn',
            'created_at': datetime.now().isoformat(),
            'items': cart
        }
        db['orders'].append(new_order)
        save_data(db)
        
        return jsonify({'success': True, 'orderId': order_id})
    
    else:
        new_order = {
            'id': order_id,
            'email': email,
            'total': total,
            'status': 'PENDING',
            'deliveryData': '',
            'created_at': datetime.now().isoformat(),
            'items': cart,
            'qrCode': f'order_{order_id}_{email}'
        }
        db['orders'].append(new_order)
        save_data(db)
        
        return jsonify({
            'success': True,
            'orderId': order_id,
            'checkoutUrl': f'/tracking?order={order_id}',
            'qrCode': f'order_{order_id}_{email}'
        })

@app.route('/api/check-order', methods=['GET'])
def check_order():
    order_id = request.args.get('id')
    db = load_data()
    
    for order in db['orders']:
        if order['id'] == order_id:
            return jsonify(order)
    
    return jsonify({'error': 'Order not found'}), 404

@app.route('/api/user-orders', methods=['POST'])
def user_orders():
    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    req_email = data.get('email')
    
    if req_email != email:
        return jsonify({'error': 'Unauthorized'}), 401
    
    db = load_data()
    orders = [o for o in db['orders'] if o['email'] == email]
    return jsonify(orders)

# ============ TOPUP ============
@app.route('/api/topup', methods=['POST'])
def topup():
    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    card_number = data.get('cardNumber')
    card_serial = data.get('cardSerial')
    card_type = data.get('cardType')
    card_value = int(data.get('cardValue', 0))
    
    # Nếu có API key thì gọi thật, nếu không thì mô phỏng
    if PARTNER_ID and PARTNER_KEY:
        return topup_with_api(email, card_number, card_serial, card_type, card_value)
    else:
        # Mô phỏng nạp thẻ
        db = load_data()
        db['balances'][email] = db['balances'].get(email, 0) + card_value
        db['topups'].append({
            'email': email,
            'card_type': card_type,
            'declared_value': card_value,
            'amount_received': card_value,
            'status': 'success',
            'created_at': datetime.now().isoformat()
        })
        save_data(db)
        
        return jsonify({
            'success': True,
            'message': 'Nạp thẻ thành công',
            'newBalance': db['balances'][email]
        })

def topup_with_api(email, card_number, card_serial, card_type, card_value):
    # Tạo chữ ký
    request_id = str(int(datetime.now().timestamp()))
    raw_sign = PARTNER_KEY + card_type + card_number + card_serial + str(card_value) + request_id
    sign = hashlib.md5(raw_sign.encode()).hexdigest()
    
    payload = {
        'telco': card_type,
        'code': card_number,
        'serial': card_serial,
        'amount': str(card_value),
        'request_id': request_id,
        'partner_id': PARTNER_ID,
        'sign': sign,
        'command': 'charging'
    }
    
    try:
        response = requests.post('https://thesieure.com/chargingws/v2', data=payload, timeout=30)
        result = response.json()
        
        if result.get('status') == 1:
            real_value = int(result.get('value', card_value))
            db = load_data()
            db['balances'][email] = db['balances'].get(email, 0) + real_value
            db['topups'].append({
                'email': email,
                'card_type': card_type,
                'declared_value': card_value,
                'amount_received': real_value,
                'status': 'success',
                'created_at': datetime.now().isoformat()
            })
            save_data(db)
            
            return jsonify({
                'success': True,
                'message': f'Nạp thành công {real_value}đ',
                'newBalance': db['balances'][email]
            })
        else:
            return jsonify({
                'success': False,
                'message': result.get('message', 'Thẻ không hợp lệ')
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Lỗi kết nối: {str(e)}'
        }), 500

# ============ CALLBACK THESIEURE ============
@app.route('/api/thesieure-callback', methods=['POST'])
def thesieure_callback():
    """
    TheSieuRe gửi kết quả về đây
    """
    data = request.json
    print("📩 Nhận callback từ TheSieuRe:", data)
    
    status = data.get('status')
    request_id = data.get('request_id')
    email = data.get('email')
    value = data.get('value')
    
    if status == 1 and email:
        db = load_data()
        db['balances'][email] = db['balances'].get(email, 0) + int(value)
        db['topups'].append({
            'email': email,
            'amount': value,
            'status': 'callback_success',
            'created_at': datetime.now().isoformat()
        })
        save_data(db)
        print(f"✅ Nạp thành công {value}đ cho {email}")
        return jsonify({'success': True}), 200
    
    return jsonify({'success': False}), 200

# ============ CREATE TOPUP QR ============
@app.route('/api/create-topup-qr', methods=['POST'])
def create_topup_qr():
    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    amount = int(data.get('amount', 0))
    
    order_id = str(int(datetime.now().timestamp()))
    
    return jsonify({
        'success': True,
        'orderId': order_id,
        'qrCode': f'topup_{order_id}_{email}_{amount}'
    })

@app.route('/api/check-topup', methods=['GET'])
def check_topup():
    order_id = request.args.get('id')
    return jsonify({'status': 'PAID', 'amount': 50000})

# ============ SERVE HTML ============
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/admin.html')
def serve_admin():
    return send_from_directory('.', 'admin.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# ============ RUN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
