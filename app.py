import os
import hashlib
import requests
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, session, send_from_directory, redirect
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = 'your-secret-key-change-this'
CORS(app, supports_credentials=True)

# ============ DATABASE ============
DATA_FILE = 'data.json'

def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {'users': [], 'products': [], 'orders': [], 'balances': {}, 'topups': [], 'news': [], 'manual_payments': []}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def formatVND(num):
    return f"{int(num):,}đ"

if not os.path.exists(DATA_FILE):
    save_data({'users': [], 'products': [], 'orders': [], 'balances': {}, 'topups': [], 'news': [], 'manual_payments': []})

# ============ CẤU HÌNH ============
ADMIN_USERNAME = 'adminproxyvip'
ADMIN_PASSWORD = 'ndlxtp'

# TheSieuRe - Nạp thẻ
THE_SIEU_RE_PARTNER_ID = '48133853439'
THE_SIEU_RE_PARTNER_KEY = '0575fbad2a38b22febddee3344fa11b6'

# Google OAuth
GOOGLE_CLIENT_ID = '818511008345-nkc6m1tt8ksluo8131qh4im977bnej1g.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = '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'
GOOGLE_REDIRECT_URI = 'https://ten-ban.onrender.com/api/auth/google-callback'

# ============ GOOGLE OAUTH ============
oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    userinfo_url='https://www.googleapis.com/oauth2/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
)

# ============ ADMIN AUTH ============
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
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    db = load_data()
    return jsonify(db.get('orders', []))

@app.route('/api/admin/update-order', methods=['POST'])
def admin_update_order():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
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
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    db = load_data()
    result = []
    for email, balance in db['balances'].items():
        result.append({'email': email, 'balance': balance})
    return jsonify(result)

@app.route('/api/admin/topup-list', methods=['GET'])
def admin_topup_list():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    db = load_data()
    return jsonify(db.get('topups', []))

@app.route('/api/admin/adjust-balance', methods=['POST'])
def admin_adjust_balance():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    email = data.get('email')
    amount = int(data.get('amount', 0))
    
    db = load_data()
    db['balances'][email] = db['balances'].get(email, 0) + amount
    save_data(db)
    
    return jsonify({'success': True, 'newBalance': db['balances'][email]})

@app.route('/api/admin/revenue', methods=['GET'])
def admin_revenue():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    db = load_data()
    orders = db.get('orders', [])
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
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify([])

# ============ MANUAL PAYMENT - ADMIN ============
@app.route('/api/admin/manual-payments', methods=['GET'])
def admin_manual_payments():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    db = load_data()
    return jsonify(db.get('manual_payments', []))

@app.route('/api/admin/confirm-manual-payment', methods=['POST'])
def confirm_manual_payment():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    payment_id = data.get('paymentId')
    
    db = load_data()
    payments = db.get('manual_payments', [])
    
    for payment in payments:
        if payment['id'] == payment_id and payment['status'] == 'PENDING':
            email = payment['email']
            amount = payment['amount']
            db['balances'][email] = db['balances'].get(email, 0) + amount
            payment['status'] = 'PAID'
            save_data(db)
            return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Không tìm thấy yêu cầu'}), 404

# ============ ADD PRODUCT ============
@app.route('/api/admin/add-product', methods=['POST'])
def add_product():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
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
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
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

# ============ GOOGLE LOGIN ============
@app.route('/api/auth/google')
def google_login():
    if not GOOGLE_CLIENT_ID:
        return "Google Client ID chưa được cấu hình!", 500
    return google.authorize_redirect(GOOGLE_REDIRECT_URI)

@app.route('/api/auth/google-callback')
def google_callback():
    try:
        token = google.authorize_access_token()
        resp = google.get('https://www.googleapis.com/oauth2/v1/userinfo')
        user_info = resp.json()
        
        email = user_info.get('email')
        name = user_info.get('name', email.split('@')[0])
        picture = user_info.get('picture', '')
        
        if not email:
            return redirect('/login?error=no_email')
        
        db = load_data()
        user_exists = False
        
        for user in db['users']:
            if user['email'] == email:
                user_exists = True
                break
        
        if not user_exists:
            new_user = {
                'id': str(uuid.uuid4()),
                'email': email,
                'password': '',
                'display_name': name,
                'avatar': picture,
                'created_at': datetime.now().isoformat(),
                'auth_provider': 'google'
            }
            db['users'].append(new_user)
            db['balances'][email] = 0
            save_data(db)
        
        session['user_email'] = email
        return redirect('/')
    
    except Exception as e:
        print(f"❌ Google login error: {e}")
        return redirect('/login?error=google_auth_failed')

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

# ============ TOPUP - NẠP THẺ CÀO ============
@app.route('/api/topup', methods=['POST'])
def topup():
    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    telco = data.get('cardType')
    code = data.get('cardNumber')
    serial = data.get('cardSerial')
    amount = int(data.get('cardValue', 0))
    request_id = str(int(datetime.now().timestamp()))
    
    if not telco or not code or not serial or not amount:
        return jsonify({
            'success': False,
            'message': 'Vui lòng nhập đầy đủ thông tin thẻ!'
        }), 400
    
    raw_sign = THE_SIEU_RE_PARTNER_KEY + telco + code + serial + str(amount) + request_id
    sign = hashlib.md5(raw_sign.encode()).hexdigest()
    
    url = "https://thesieure.com/chargingws/v2"
    params = {
        'partner_id': THE_SIEU_RE_PARTNER_ID,
        'telco': telco,
        'code': code,
        'serial': serial,
        'amount': str(amount),
        'request_id': request_id,
        'sign': sign,
        'command': 'charging'
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        result = response.json()
        
        db = load_data()
        
        if result.get('status') == 1:
            real_value = int(result.get('value', amount))
            db['balances'][email] = db['balances'].get(email, 0) + real_value
            
            db['topups'].append({
                'email': email,
                'card_type': telco,
                'declared_value': amount,
                'amount_received': real_value,
                'status': 'success',
                'request_id': request_id,
                'created_at': datetime.now().isoformat()
            })
            save_data(db)
            
            return jsonify({
                'success': True,
                'message': f'Nạp thành công {formatVND(real_value)}',
                'newBalance': db['balances'][email]
            })
        else:
            error_msg = result.get('message', 'Thẻ không hợp lệ!')
            db['topups'].append({
                'email': email,
                'card_type': telco,
                'declared_value': amount,
                'amount_received': 0,
                'status': 'failed',
                'message': error_msg,
                'request_id': request_id,
                'created_at': datetime.now().isoformat()
            })
            save_data(db)
            
            return jsonify({
                'success': False,
                'message': error_msg
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Lỗi kết nối: {str(e)}'
        }), 500

# ============ MANUAL PAYMENT - USER ============
@app.route('/api/manual-payment-notify', methods=['POST'])
def manual_payment_notify():
    data = request.json
    email = data.get('email')
    amount = data.get('amount')
    bank_account = data.get('bank_account')
    bank_name = data.get('bank_name')
    
    db = load_data()
    
    if 'manual_payments' not in db:
        db['manual_payments'] = []
    
    db['manual_payments'].append({
        'id': str(int(datetime.now().timestamp())),
        'email': email,
        'amount': amount,
        'bank_account': bank_account,
        'bank_name': bank_name,
        'status': 'PENDING',
        'created_at': datetime.now().isoformat(),
        'message': f'Khách hàng {email} đã chuyển khoản {formatVND(amount)} vào tài khoản {bank_account}'
    })
    
    save_data(db)
    
    return jsonify({'success': True})

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
