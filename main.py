from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from divenendoj import tobeguessed
from random import choice
import datetime, requests

app = Flask(__name__)
app.config['SECRET_KEY'] = '1284'
socketio = SocketIO(app, template_folder="templates")

words = []
connected_users = []
chat = []
current_user = None
current_word = ''

def ip2name(ip):
    url = f'http://ip-api.com/json/{ip}'
    response = requests.get(url)
    return response.json()['city'] + ip.split('.')[-1]

def userip2name(ip):
    for u in connected_users:
        if u['ip'] == ip:
            return u['nickname']
    return '????'

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html',
                           words=words,
                           current_user=current_user)

@app.route('/get_words', methods=['GET'])
def get_words():
    return jsonify({'words': words})

@socketio.on('button_click')
def handle_button_click(data):
    word, cursor = data['word'], data['cursor']
    if cursor:
        words.insert(cursor, word)
    else:
        words.append(word)
    emit('word_added', {'words': words}, broadcast=True)

@socketio.on('pop_button_click')
def handle_pop_button_click(data):
    cursor = data['cursor']
    global words
    if cursor:
        words = words[:cursor - 1] + words[cursor:]
    else:
        words = words[:-1]
    emit('word_added', {'words': words}, broadcast=True)

@socketio.on('clear_button_click')
def handle_clear_button_click():
    words.clear()
    emit('word_added', {'words': words}, broadcast=True)

@socketio.on('connect')
def handle_connect():
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    print(f'New player connected: {user_ip}')

    # Check if user already exists
    user = next((u for u in connected_users if u['ip'] == user_ip), None)

    if user is None:
        user = {'ip': user_ip,
                'points': 0,
                'online': True,
                'nickname': ip2name(user_ip)}
        connected_users.append(user)
    else:
        user['online'] = True

    global current_user
    if current_user is None or not next((u for u in connected_users if u['ip'] == current_user), None)['online']:
        current_user = user['ip']

    emit('user_list', {'users': [u for u in connected_users if u['online']]}, broadcast=True)
    emit('ip_address', {'ip': user_ip})
    emit('current', {'current_ip': current_user, 'word': current_word}, broadcast=True)
    emit('word_added', {'words': words}, broadcast=True)
    emit('update_chat', {'chat': chat}, broadcast=True)
    
@socketio.on('disconnect')
def handle_disconnect():
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    user = next((u for u in connected_users if u['ip'] == user_ip), None)
    if user:
        user['online'] = False
        emit('user_list', {'users': [u for u in connected_users if u['online']]}, broadcast=True)

#@socketio.on('next_user')
def handle_next_user(data):
    global current_user
    guessed_ip = data['ip']

    for user in connected_users:
        if user['ip'] == guessed_ip or user['ip'] == current_user:
            user['points'] += 1

    with open('logs.txt', 'a') as f:
        f.write(f'{str(datetime.datetime.now())}\n')
        f.write(f'{current_word}! {current_user} {userip2name(current_user)} → {guessed_ip} {userip2name(guessed_ip)}\n')
        f.write(f'{words}\n')
        f.write(f'{connected_users}\n\n')

    current_user = guessed_ip
    emit('user_list', {'users': [u for u in connected_users if u['online']]}, broadcast=True)
    emit('current', {'current_ip': current_user, 'word': current_word}, broadcast=True)

@socketio.on('new_guessed_word')
def update_guessed_word():
    global current_word
    current_word = choice(tobeguessed)
    emit('current', {'current_ip': current_user, 'word': current_word}, broadcast=True)

@socketio.on('append_message')
def handle_append_message(data):
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    if user_ip != current_user:
        chat.append((user_ip, data['message']))
        emit('update_chat', {'chat': chat}, broadcast=True)
        if data['message'].lower().strip().replace('ё', 'е') == current_word.replace('ё', 'е'):
            chat.append(('_sys_', f'{current_word}! {userip2name(current_user)} → {userip2name(user_ip)}'))
            emit('update_chat', {'chat': chat}, broadcast=True)
            emit('yay', 
                 {'old': current_user, 'new': user_ip, 'word': current_word}, broadcast=True)
            handle_next_user({'ip': user_ip})
            update_guessed_word()

@socketio.on('edit_points')
def handle_edit_points(data):
    user = next((u for u in connected_users if u['ip'] == data['ip']), None)
    if user:
        user['points'] += data['delta']
    with open('logs.txt', 'a') as f:
        f.write(f'{str(datetime.datetime.now())}\n')
        f.write(f"{data['ip']} gained {data['delta']} points\n\n")
    emit('user_list', {'users': [u for u in connected_users if u['online']]}, broadcast=True)

if __name__ == '__main__':
    print('Starting...')
    app.secret_key = 'your-secret-key'
    with open('logs.txt', 'a') as f:
        f.write(f'\n\nSESSION STARTED at {str(datetime.datetime.now())}\n')
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
