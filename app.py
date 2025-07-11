# app.py - 主程式檔案（每次重啟需重新登入）
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
# from linebot import LineBotApi, WebhookHandler
# from linebot.exceptions import InvalidSignatureError
# from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import os
import secrets
from datetime import datetime, timedelta
import json
from functools import wraps

# Flask 應用程式設定
app = Flask(__name__)

# 動態生成 SECRET_KEY，每次重啟都不同
app.config['SECRET_KEY'] = secrets.token_hex(32)  # 每次啟動生成新的 64 字元密鑰

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 管理員密碼設定（生產環境建議使用環境變數）
ADMIN_PASSWORD = 'admin123'  # 請在生產環境中更換為安全密碼

# 初始化擴充套件
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# LINE Bot 設定 (暫時用假的 token，等有真的再換)
LINE_CHANNEL_ACCESS_TOKEN = 'YOUR_CHANNEL_ACCESS_TOKEN'
LINE_CHANNEL_SECRET = 'YOUR_CHANNEL_SECRET'

# 啟動時印出新的 SECRET_KEY 資訊（僅用於除錯）
print(f"🔑 新的 SECRET_KEY 已生成: {app.config['SECRET_KEY'][:16]}...")
print("⚠️  重啟後所有 Session 將失效，需重新登入")


# ========================
# 權限裝飾器
# ========================

def admin_required(f):
    """管理員權限裝飾器"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('請先登入管理員帳號', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)

    return decorated_function


# ========================
# 資料庫模型（保持不變）
# ========================

class MenuItem(db.Model):
    """菜單項目"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Integer, nullable=False)  # 以分為單位
    category = db.Column(db.String(50), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    image_url = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'category': self.category,
            'is_available': self.is_available,
            'image_url': self.image_url
        }


class Order(db.Model):
    """訂單"""
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(100), nullable=False)
    customer_name = db.Column(db.String(100))
    contact_phone = db.Column(db.String(20))
    total_amount = db.Column(db.Integer, nullable=False)
    delivery_type = db.Column(db.String(20), nullable=False)  # dine-in, takeout, delivery
    delivery_address = db.Column(db.Text)
    table_number = db.Column(db.String(10))
    order_status = db.Column(db.String(20), default='pending')  # pending, preparing, ready, completed, cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 關聯
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'line_user_id': self.line_user_id,
            'customer_name': self.customer_name,
            'contact_phone': self.contact_phone,
            'total_amount': self.total_amount,
            'delivery_type': self.delivery_type,
            'delivery_address': self.delivery_address,
            'table_number': self.table_number,
            'order_status': self.order_status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'items': [item.to_dict() for item in self.items]
        }


class OrderItem(db.Model):
    """訂單明細"""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Integer, nullable=False)

    # 關聯
    menu_item = db.relationship('MenuItem', backref='order_items')

    def to_dict(self):
        return {
            'id': self.id,
            'menu_item_id': self.menu_item_id,
            'menu_item_name': self.menu_item.name,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'subtotal': self.subtotal
        }


# ========================
# LINE Bot 相關函數（保持不變）
# ========================

def send_order_confirmation(line_user_id, order):
    """發送訂單確認訊息 - 目前只印出來，不實際發送"""
    try:
        items_text = "\n".join([
            f"{item.menu_item.name} x{item.quantity} - NT$ {item.subtotal}"
            for item in order.items
        ])

        delivery_info = ""
        if order.delivery_type == "dine-in":
            delivery_info = f"內用點餐 - 桌號: {order.table_number}"
        elif order.delivery_type == "takeout":
            delivery_info = "外帶取餐"
        elif order.delivery_type == "delivery":
            delivery_info = f"外送服務\n地址: {order.delivery_address}"

        message_text = f"""🎉 訂單確認成功！

訂單編號: #{order.id}
{items_text}

{delivery_info}
總金額: NT$ {order.total_amount}
預計準備時間: 15-20分鐘

感謝您的訂購！"""

        print(f"=== LINE 訊息模擬 ===")
        print(f"發送給用戶: {line_user_id}")
        print(message_text)
        print("==================")

    except Exception as e:
        print(f"發送確認訊息失敗: {e}")


def send_status_update(line_user_id, order_id, status):
    """發送訂單狀態更新 - 目前只印出來，不實際發送"""
    try:
        status_messages = {
            'preparing': '您的訂單正在製作中，請稍候...',
            'ready': '您的訂單已製作完成，請前來取餐！',
            'completed': '感謝您的訂購，歡迎再次光臨！'
        }

        if status in status_messages:
            message_text = f"訂單 #{order_id} 狀態更新：\n{status_messages[status]}"
            print(f"=== LINE 狀態更新模擬 ===")
            print(f"發送給用戶: {line_user_id}")
            print(message_text)
            print("======================")

    except Exception as e:
        print(f"發送狀態更新失敗: {e}")


# ========================
# 管理員驗證路由
# ========================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """管理員登入頁面"""
    # 如果已經登入，直接跳轉到後台
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        password = request.form.get('password')

        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session['admin_login_time'] = datetime.now().isoformat()
            session['server_start_time'] = datetime.now().isoformat()  # 記錄伺服器啟動時間
            flash('登入成功！', 'success')
            print(f"✅ 管理員於 {datetime.now().strftime('%H:%M:%S')} 登入成功")
            return redirect(url_for('admin_dashboard'))
        else:
            flash('密碼錯誤，請重新輸入', 'error')
            print(f"❌ 管理員登入失敗 - 密碼錯誤")

    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    """管理員登出"""
    session.pop('admin_logged_in', None)
    session.pop('admin_login_time', None)
    session.pop('server_start_time', None)
    flash('已成功登出', 'info')
    print(f"📤 管理員於 {datetime.now().strftime('%H:%M:%S')} 登出")
    return redirect(url_for('admin_login'))


# ========================
# 客戶端路由
# ========================

@app.route('/')
def index():
    """首頁 - 點餐介面（客戶專用）"""
    menu_items = MenuItem.query.filter_by(is_available=True).all()
    categories = db.session.query(MenuItem.category).distinct().all()
    return render_template('menu.html',
                           menu_items=menu_items,
                           categories=[cat[0] for cat in categories])


# ========================
# 管理員路由（需要驗證）
# ========================

@app.route('/admin')
@admin_required
def admin_dashboard():
    """後台管理首頁（需要管理員權限）"""
    try:
        # 使用本地時間，確保一致性
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
        today_end = today_start + timedelta(days=1)

        # 查詢今日訂單（使用時間範圍比較）
        today_orders = Order.query.filter(
            Order.created_at >= today_start,
            Order.created_at < today_end
        ).all()

        # 分別計算不同狀態的訂單
        completed_today_orders = [order for order in today_orders if order.order_status == 'completed']
        pending_orders = [order for order in today_orders if order.order_status == 'pending']

        # 計算營業額（只計算已完成訂單）
        completed_today_revenue = sum(order.total_amount for order in completed_today_orders)

        stats = {
            'today_orders': len(today_orders),
            'today_revenue': completed_today_revenue,
            'pending_orders': len(pending_orders),
            'completed_orders': len(completed_today_orders)
        }

        # 查詢所有訂單，包含關聯的訂單明細和菜單項目
        orders = Order.query.options(
            db.joinedload(Order.items).joinedload(OrderItem.menu_item)
        ).order_by(Order.created_at.desc()).limit(50).all()

        return render_template('admin.html', stats=stats, orders=orders)

    except Exception as e:
        print(f"❌ 後台查詢失敗: {e}")
        # 回傳空資料避免頁面錯誤
        return render_template('admin.html',
                               stats={'today_orders': 0, 'today_revenue': 0, 'pending_orders': 0,
                                      'completed_orders': 0},
                               orders=[])


# ========================
# API 路由
# ========================

@app.route('/api/orders', methods=['POST'])
def create_order():
    """建立新訂單"""
    try:
        data = request.get_json()

        # 建立訂單
        order = Order(
            line_user_id=data.get('line_user_id'),
            customer_name=data.get('customer_name'),
            contact_phone=data.get('contact_phone'),
            total_amount=data.get('total_amount'),
            delivery_type=data.get('delivery_type'),
            delivery_address=data.get('delivery_address'),
            table_number=data.get('table_number'),
            notes=data.get('notes')
        )

        db.session.add(order)
        db.session.flush()  # 取得 order.id

        # 建立訂單明細
        for item_data in data.get('items', []):
            order_item = OrderItem(
                order_id=order.id,
                menu_item_id=item_data['menu_item_id'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                subtotal=item_data['subtotal']
            )
            db.session.add(order_item)

        db.session.commit()

        # 發送 LINE 確認訊息 (模擬)
        if order.line_user_id:
            send_order_confirmation(order.line_user_id, order)

        return jsonify({
            'success': True,
            'order_id': order.id,
            'message': '訂單建立成功'
        })

    except Exception as e:
        db.session.rollback()
        print(f"建立訂單失敗: {e}")
        return jsonify({
            'success': False,
            'message': '訂單建立失敗'
        }), 500


@app.route('/api/orders/<int:order_id>/status', methods=['PATCH'])
@admin_required
def update_order_status(order_id):
    """更新訂單狀態（需要管理員權限）"""
    try:
        data = request.get_json()
        new_status = data.get('status')

        order = Order.query.get_or_404(order_id)
        order.order_status = new_status
        order.updated_at = datetime.now()

        db.session.commit()

        # 發送狀態更新通知 (模擬)
        if order.line_user_id:
            send_status_update(order.line_user_id, order_id, new_status)

        return jsonify({
            'success': True,
            'message': '訂單狀態更新成功'
        })

    except Exception as e:
        db.session.rollback()
        print(f"更新訂單狀態失敗: {e}")
        return jsonify({
            'success': False,
            'message': '更新失敗'
        }), 500


@app.route('/api/menu')
def get_menu():
    """取得菜單"""
    category = request.args.get('category')
    query = MenuItem.query.filter_by(is_available=True)

    if category:
        query = query.filter_by(category=category)

    menu_items = query.all()
    return jsonify([item.to_dict() for item in menu_items])


# ========================
# 除錯路由（需要管理員權限）
# ========================

@app.route('/debug')
@admin_required
def debug_info():
    """除錯資訊頁面（需要管理員權限）"""
    try:
        # 統計資料
        menu_count = MenuItem.query.count()
        order_count = Order.query.count()
        order_item_count = OrderItem.query.count()

        # 所有訂單（包含關聯資料）
        orders = Order.query.options(
            db.joinedload(Order.items).joinedload(OrderItem.menu_item)
        ).order_by(Order.created_at.desc()).all()

        # Session 資訊
        session_info = {
            'admin_logged_in': session.get('admin_logged_in', False),
            'admin_login_time': session.get('admin_login_time', 'N/A'),
            'server_start_time': session.get('server_start_time', 'N/A'),
            'secret_key_preview': app.config['SECRET_KEY'][:16] + '...'
        }

        debug_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>除錯資訊</title>
            <style>
                body {{ font-family: Arial; padding: 20px; line-height: 1.6; }}
                .info {{ background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .error {{ background: #ffeeee; color: red; }}
                .success {{ background: #eeffee; color: green; }}
                .warning {{ background: #fff3cd; color: #856404; }}
                .order-detail {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background: #f2f2f2; }}
                .btn {{ padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; }}
                .btn:hover {{ background: #0056b3; }}
                .logout {{ background: #dc3545; }}
                .logout:hover {{ background: #c82333; }}
            </style>
        </head>
        <body>
            <h1>🔍 系統除錯資訊</h1>

            <div class="info warning">
                <h3>🔑 Session 安全資訊</h3>
                <p><strong>管理員登入狀態:</strong> {session_info['admin_logged_in']}</p>
                <p><strong>登入時間:</strong> {session_info['admin_login_time']}</p>
                <p><strong>伺服器啟動時間:</strong> {session_info['server_start_time']}</p>
                <p><strong>SECRET_KEY (前16字元):</strong> {session_info['secret_key_preview']}</p>
                <p><strong>⚠️ 重啟後 SECRET_KEY 會變更，需重新登入</strong></p>
                <a href="/admin/logout" class="btn logout">登出</a>
            </div>

            <div class="info success">
                <h3>📊 資料庫統計</h3>
                <p><strong>菜單項目數量:</strong> {menu_count}</p>
                <p><strong>訂單數量:</strong> {order_count}</p>
                <p><strong>訂單明細數量:</strong> {order_item_count}</p>
                <p><strong>目前時間:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        """

        if orders:
            debug_html += f"""
            <div class="info success">
                <h3>✅ 找到 {len(orders)} 筆訂單</h3>
            </div>

            <div class="info">
                <h3>📋 詳細訂單資訊</h3>
            """

            for i, order in enumerate(orders[:5]):  # 只顯示前5筆
                debug_html += f"""
                <div class="order-detail">
                    <h4>訂單 #{order.id}</h4>
                    <p><strong>客戶:</strong> {order.customer_name or '匿名'}</p>
                    <p><strong>金額:</strong> NT$ {order.total_amount}</p>
                    <p><strong>狀態:</strong> {order.order_status}</p>
                    <p><strong>配送方式:</strong> {order.delivery_type}</p>
                    <p><strong>建立時間:</strong> {order.created_at}</p>
                    <p><strong>商品數量:</strong> {len(order.items)}</p>

                    <table>
                        <thead>
                            <tr>
                                <th>商品名稱</th>
                                <th>單價</th>
                                <th>數量</th>
                                <th>小計</th>
                            </tr>
                        </thead>
                        <tbody>
                """

                for item in order.items:
                    debug_html += f"""
                            <tr>
                                <td>{item.menu_item.name if item.menu_item else 'N/A'}</td>
                                <td>NT$ {item.unit_price}</td>
                                <td>{item.quantity}</td>
                                <td>NT$ {item.subtotal}</td>
                            </tr>
                    """

                debug_html += """
                        </tbody>
                    </table>
                </div>
                """

            debug_html += "</div>"
        else:
            debug_html += """
            <div class="info error">
                <h3>❌ 沒有找到任何訂單</h3>
                <p>可能的原因：</p>
                <ul>
                    <li>尚未建立任何訂單</li>
                    <li>資料庫查詢問題</li>
                    <li>關聯資料問題</li>
                </ul>
            </div>
            """

        debug_html += """
            <div class="info">
                <h3>🔗 測試連結</h3>
                <a href="/" class="btn">🍽️ 客戶點餐頁面</a>
                <a href="/admin" class="btn">⚙️ 後台管理</a>
                <a href="/api/menu" class="btn">📋 API: 菜單</a>
                <a href="/dev/reset-db" class="btn" style="background: #dc3545;">🗑️ 重置資料庫</a>
            </div>
        </body>
        </html>
        """

        return debug_html

    except Exception as e:
        return f"""
        <html>
        <body style="font-family: Arial; padding: 20px;">
            <h1>❌ 除錯時發生錯誤</h1>
            <p style="color: red; background: #ffeeee; padding: 15px; border-radius: 5px;">
                <strong>錯誤詳情:</strong><br>
                {str(e)}
            </p>
            <p><a href="/admin">返回後台</a> | <a href="/admin/logout">登出</a></p>
        </body>
        </html>
        """


# ========================
# 開發用工具路由（需要管理員權限）
# ========================

@app.route('/dev/reset-db')
@admin_required
def reset_database():
    """重置資料庫（僅開發環境使用，需要管理員權限）"""
    if app.debug:
        try:
            db.drop_all()
            db.create_all()
            init_db()
            flash('✅ 資料庫已重置，範例資料已建立', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f'❌ 重置失敗: {str(e)}', 'error')
            return redirect(url_for('admin_dashboard'))
    else:
        flash('僅在開發模式下可用', 'error')
        return redirect(url_for('admin_dashboard'))


# ========================
# 初始化資料（保持不變）
# ========================

def init_db():
    """初始化資料庫和範例資料"""
    with app.app_context():
        db.create_all()

        # 檢查是否已有資料
        if MenuItem.query.count() == 0:
            # 建立範例菜單
            menu_items = [
                MenuItem(name="經典牛肉堡", description="多汁牛肉排配新鮮蔬菜", price=180, category="主餐"),
                MenuItem(name="奶油培根義大利麵", description="濃郁奶油醬配脆培根", price=220, category="主餐"),
                MenuItem(name="炸雞排飯", description="酥脆炸雞排配白飯", price=150, category="主餐"),
                MenuItem(name="精品咖啡", description="現磨咖啡豆，香濃回甘", price=120, category="飲料"),
                MenuItem(name="鮮榨柳橙汁", description="100% 新鮮柳橙現榨", price=80, category="飲料"),
                MenuItem(name="珍珠奶茶", description="香濃奶茶配Q彈珍珠", price=60, category="飲料"),
                MenuItem(name="巧克力蛋糕", description="濃郁巧克力，甜而不膩", price=150, category="甜點"),
                MenuItem(name="起司蛋糕", description="滑順起司，入口即化", price=130, category="甜點"),
            ]

            for item in menu_items:
                db.session.add(item)

            db.session.commit()
            print("✅ 範例菜單已建立")
            print("📝 資料庫初始化完成")


# ========================
# 啟動應用程式
# ========================

if __name__ == '__main__':
    import os

    print("🚀 正在啟動餐廳點餐系統...")
    print("🔐 安全模式: 每次重啟需重新登入")
    init_db()
    print("🌐 請開啟瀏覽器訪問:")
    print(" 客戶點餐: http://127.0.0.1:5000/")
    print(" 後台管理: http://127.0.0.1:5000/admin/login")
    print("💡 管理員密碼: admin123")
    print("💡 按 Ctrl+C 停止服務")

    # 本地開發時使用debug模式，部署時使用環境變數
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    else:
        app.run(debug=True, port=5000, host='0.0.0.0')