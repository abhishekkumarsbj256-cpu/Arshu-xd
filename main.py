from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import requests
import time
import random
import threading
import json
import os
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Global variables for task management
active_sessions = {}
session_tasks = {}
session_logs = {}

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,/;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
    'referer': 'www.google.com'
}

def generate_session_id():
    return secrets.token_hex(8)

def validate_facebook_token(token):
    """Facebook token validate karta hai"""
    try:
        url = f"https://graph.facebook.com/v15.0/me?access_token={token}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            user_data = response.json()
            return {'valid': True, 'name': user_data.get('name', 'Unknown User'), 'id': user_data.get('id')}
        return {'valid': False}
    except:
        return {'valid': False}

def extract_page_tokens(main_token, token_name="Main Token"):
    """Facebook pages ke tokens automatically extract karta hai"""
    try:
        url = f"https://graph.facebook.com/v15.0/me/accounts?access_token={main_token}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            page_tokens = []
            
            if 'data' in data:
                for page in data['data']:
                    page_info = {
                        'name': f"{page.get('name', 'Unknown Page')} (Page)",
                        'token': page.get('access_token', ''),
                        'id': page.get('id', ''),
                        'parent_token': main_token,
                        'parent_name': token_name,
                        'type': 'page'
                    }
                    page_tokens.append(page_info)
            
            return page_tokens
        return []
    except:
        return []

def add_log(session_id, message, log_type="info"):
    """Session ke logs add karta hai"""
    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    log_entry = f"[{timestamp}] {message}"
    
    if session_id not in session_logs:
        session_logs[session_id] = []
    
    session_logs[session_id].append({"message": log_entry, "type": log_type})
    
    # Keep only last 1000 logs
    if len(session_logs[session_id]) > 1000:
        session_logs[session_id] = session_logs[session_id][-1000:]
    
    print(log_entry)

def run_commenting_task(session_id, data):
    """Main commenting task run karta hai with loop shifting"""
    thread_id = data['thread_id']
    haters_name = data['haters_name']
    speed = data['speed']
    normal_tokens = data['normal_tokens']
    shifting_tokens = data.get('shifting_tokens', [])
    shifting_time = data.get('shifting_time', 0)
    messages = data['messages']
    
    add_log(session_id, f"🚀 Task started for Post ID: {thread_id}")
    add_log(session_id, f"📊 Normal Tokens: {len(normal_tokens)} | Shifting Tokens: {len(shifting_tokens)}")
    add_log(session_id, f"💬 Messages: {len(messages)} | Speed: {speed}s | Shifting Time: {shifting_time}h")
    
    # Extract page tokens for both normal and shifting tokens
    all_normal_tokens = []
    all_shifting_tokens = []
    
    # Process normal tokens
    for token_info in normal_tokens:
        all_normal_tokens.append(token_info)
        if token_info.get('type') != 'page':
            page_tokens = extract_page_tokens(token_info['token'], token_info['name'])
            for page in page_tokens:
                if page['token'] not in [t['token'] for t in all_normal_tokens]:
                    all_normal_tokens.append(page)
                    add_log(session_id, f"✅ Auto-added page token: {page['name']}")
    
    # Process shifting tokens
    for token_info in shifting_tokens:
        all_shifting_tokens.append(token_info)
        if token_info.get('type') != 'page':
            page_tokens = extract_page_tokens(token_info['token'], token_info['name'])
            for page in page_tokens:
                if page['token'] not in [t['token'] for t in all_shifting_tokens]:
                    all_shifting_tokens.append(page)
                    add_log(session_id, f"🔄 Auto-added shifting page token: {page['name']}")
    
    add_log(session_id, f"📈 Final Count - Normal: {len(all_normal_tokens)} | Shifting: {len(all_shifting_tokens)}")
    
    # Token statistics
    normal_main_tokens = [t for t in all_normal_tokens if t.get('type') != 'page']
    normal_page_tokens = [t for t in all_normal_tokens if t.get('type') == 'page']
    shifting_main_tokens = [t for t in all_shifting_tokens if t.get('type') != 'page']
    shifting_page_tokens = [t for t in all_shifting_tokens if t.get('type') == 'page']
    
    add_log(session_id, f"👤 Normal - Main: {len(normal_main_tokens)} | Pages: {len(normal_page_tokens)}")
    add_log(session_id, f"🔄 Shifting - Main: {len(shifting_main_tokens)} | Pages: {len(shifting_page_tokens)}")
    
    start_time = time.time()
    last_shift_time = start_time
    use_normal_tokens = True
    shift_count = 0
    
    failed_tokens = []
    comment_count = 0
    successful_comments = 0
    
    while active_sessions.get(session_id, {}).get('running', False):
        try:
            # Loop shifting logic
            current_time = time.time()
            if shifting_time > 0 and (current_time - last_shift_time) >= shifting_time * 3600:
                use_normal_tokens = not use_normal_tokens
                last_shift_time = current_time
                shift_count += 1
                current_set = "NORMAL" if use_normal_tokens else "SHIFTING"
                add_log(session_id, f"🔄 Token shifting activated! Now using: {current_set} tokens (Shift #{shift_count})")
            
            # Select current token set
            if use_normal_tokens:
                current_tokens = all_normal_tokens
                token_set_name = "NORMAL"
            else:
                current_tokens = all_shifting_tokens if all_shifting_tokens else all_normal_tokens
                token_set_name = "SHIFTING"
            
            # Remove failed tokens from current set
            active_tokens = [token for token in current_tokens 
                           if token['token'] not in failed_tokens]
            
            if not active_tokens:
                add_log(session_id, f"⚠️ All {token_set_name} tokens failed, retrying in 60 seconds")
                time.sleep(60)
                failed_tokens = []  # Reset failed tokens
                continue
            
            # Random message select karo
            message = random.choice(messages).strip()
            full_comment = haters_name + ' ' + message
            
            # Random token select karo
            selected_token = random.choice(active_tokens)
            token_str = selected_token['token']
            token_name = selected_token['name']
            token_type = selected_token.get('type', 'main')
            
            # Post URL
            post_url = f'https://graph.facebook.com/v15.0/{thread_id}/comments'
            
            parameters = {
                'access_token': token_str,
                'message': full_comment
            }
            
            # Dynamic delay - random add karo
            dynamic_delay = speed + random.randint(5, 15)
            
            # Comment send karo with retry mechanism
            max_retries = 2
            success = False
            response_status = 0
            
            for retry in range(max_retries):
                try:
                    response = requests.post(post_url, json=parameters, headers=headers, timeout=30)
                    response_status = response.status_code
                    
                    if response.status_code == 200:
                        success = True
                        successful_comments += 1
                        
                        # Success log with green color indication
                        success_msg = f"✅ COMMENT SENT | Token: {token_name} | Set: {token_set_name} | Comment: {full_comment[:50]}..."
                        add_log(session_id, success_msg, "success")
                        break
                    else:
                        error_msg = f"🔄 Retry {retry+1}/{max_retries} | Status: {response.status_code}"
                        add_log(session_id, error_msg, "warning")
                        time.sleep(5)
                        
                except Exception as e:
                    error_msg = f"🔄 Retry {retry+1}/{max_retries} | Error: {str(e)}"
                    add_log(session_id, error_msg, "warning")
                    time.sleep(5)
            
            if not success:
                fail_msg = f"❌ Token temporarily blocked: {token_name} | Status: {response_status}"
                add_log(session_id, fail_msg, "error")
                failed_tokens.append(token_str)
            
            comment_count += 1
            
            # Update session stats
            active_sessions[session_id]['stats'] = {
                'total_comments': comment_count,
                'successful_comments': successful_comments,
                'failed_tokens': len(failed_tokens),
                'active_tokens': len(active_tokens),
                'token_set': token_set_name,
                'shift_count': shift_count,
                'normal_tokens_total': len(all_normal_tokens),
                'shifting_tokens_total': len(all_shifting_tokens)
            }
            
            # Random sleep with dynamic delay
            time.sleep(dynamic_delay)
            
            # Periodically validate and remove invalid tokens
            if comment_count % 20 == 0:
                # Validate current tokens and remove invalid ones
                valid_tokens = []
                for token_info in current_tokens:
                    validation = validate_facebook_token(token_info['token'])
                    if validation['valid']:
                        valid_tokens.append(token_info)
                    else:
                        add_log(session_id, f"🗑️ Removing invalid token: {token_info['name']}", "error")
                
                if use_normal_tokens:
                    all_normal_tokens[:] = valid_tokens
                else:
                    all_shifting_tokens[:] = valid_tokens
                
                # Reset failed tokens every 30 comments
                failed_tokens = []
                add_log(session_id, f"🔄 Token validation completed. Failed tokens reset.")
                
        except Exception as e:
            error_msg = f"💥 System Error: {str(e)}"
            add_log(session_id, error_msg, "error")
            time.sleep(30)
    
    add_log(session_id, f"🛑 Task stopped. Total: {successful_comments} successful comments")

@app.route('/')
def index():
    return '''
<!DOCTYPE html>
<html lang="en">  
<head>  
    <meta charset="utf-8">  
    <meta name="viewport" content="width=device-width, initial-scale=1.0">  
    <title>ARNAV POST - ADVANCED</title>  
    <style>
        @keyframes rotate {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        @keyframes moveBackground {
            0% { background-position: 0% 0%; }
            50% { background-position: 100% 100%; }
            100% { background-position: 0% 0%; }
        }
        
        @keyframes glowEffect1 {
            0% { box-shadow: 0 0 5px #ff0000, 0 0 10px #ff0000, 0 0 15px #ff0000, 0 0 20px #ff0000; }
            50% { box-shadow: 0 0 10px #ff0000, 0 0 20px #ff0000, 0 0 30px #ff0000, 0 0 40px #ff0000; }
            100% { box-shadow: 0 0 5px #ff0000, 0 0 10px #ff0000, 0 0 15px #ff0000, 0 0 20px #ff0000; }
        }
        
        @keyframes glowEffect2 {
            0% { box-shadow: 0 0 5px #00ff00, 0 0 10px #00ff00, 0 0 15px #00ff00, 0 0 20px #00ff00; }
            50% { box-shadow: 0 0 10px #00ff00, 0 0 20px #00ff00, 0 0 30px #00ff00, 0 0 40px #00ff00; }
            100% { box-shadow: 0 0 5px #00ff00, 0 0 10px #00ff00, 0 0 15px #00ff00, 0 0 20px #00ff00; }
        }
        
        @keyframes glowEffect3 {
            0% { box-shadow: 0 0 5px #0000ff, 0 0 10px #0000ff, 0 0 15px #0000ff, 0 0 20px #0000ff; }
            50% { box-shadow: 0 0 10px #0000ff, 0 0 20px #0000ff, 0 0 30px #0000ff, 0 0 40px #0000ff; }
            100% { box-shadow: 0 0 5px #0000ff, 0 0 10px #0000ff, 0 0 15px #0000ff, 0 0 20px #0000ff; }
        }
        
        @keyframes glowEffect4 {
            0% { box-shadow: 0 0 5px #ffff00, 0 0 10px #ffff00, 0 0 15px #ffff00, 0 0 20px #ffff00; }
            50% { box-shadow: 0 0 10px #ffff00, 0 0 20px #ffff00, 0 0 30px #ffff00, 0 0 40px #ffff00; }
            100% { box-shadow: 0 0 5px #ffff00, 0 0 10px #ffff00, 0 0 15px #ffff00, 0 0 20px #ffff00; }
        }
        
        @keyframes glowEffect5 {
            0% { box-shadow: 0 0 5px #ff00ff, 0 0 10px #ff00ff, 0 0 15px #ff00ff, 0 0 20px #ff00ff; }
            50% { box-shadow: 0 0 10px #ff00ff, 0 0 20px #ff00ff, 0 0 30px #ff00ff, 0 0 40px #ff00ff; }
            100% { box-shadow: 0 0 5px #ff00ff, 0 0 10px #ff00ff, 0 0 15px #ff00ff, 0 0 20px #ff00ff; }
        }
        
        @keyframes glowEffect6 {
            0% { box-shadow: 0 0 5px #00ffff, 0 0 10px #00ffff, 0 0 15px #00ffff, 0 0 20px #00ffff; }
            50% { box-shadow: 0 0 10px #00ffff, 0 0 20px #00ffff, 0 0 30px #00ffff, 0 0 40px #00ffff; }
            100% { box-shadow: 0 0 5px #00ffff, 0 0 10px #00ffff, 0 0 15px #00ffff, 0 0 20px #00ffff; }
        }
        
        @keyframes glowEffect7 {
            0% { box-shadow: 0 0 5px #ff8000, 0 0 10px #ff8000, 0 0 15px #ff8000, 0 0 20px #ff8000; }
            50% { box-shadow: 0 0 10px #ff8000, 0 0 20px #ff8000, 0 0 30px #ff8000, 0 0 40px #ff8000; }
            100% { box-shadow: 0 0 5px #ff8000, 0 0 10px #ff8000, 0 0 15px #ff8000, 0 0 20px #ff8000; }
        }
        
        body {
            background: url('https://i.ibb.co/zTXsn6Lz/e6d167d525b7870daf2023da9cd462af.jpg') no-repeat center center fixed;
            background-size: cover;
            color: #00ffff;
            font-family: 'Arial', sans-serif;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            position: relative;
        }
        
        body::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            z-index: -1;
        }
        
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: rgba(0, 20, 40, 0.85);
            padding: 20px;
            border-radius: 15px;
            border: 2px solid #00ffff;
            box-shadow: 0 0 30px #00ffff;
            position: relative;
            z-index: 1;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .header h1 {
            color: #00ffff;
            text-shadow: 0 0 15px #00ffff, 0 0 25px #00ffff;
            margin: 10px 0;
            font-size: 2.5em;
        }
        
        .header h2 {
            color: #ff0000;
            text-shadow: 0 0 10px #ff0000, 0 0 20px #ff0000;
            font-size: 1.8em;
        }
        
        .form-group {
            margin-bottom: 25px;
            position: relative;
        }
        
        label {
            color: #00ffff;
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            text-shadow: 0 0 5px #00ffff;
            font-size: 1.1em;
        }
        
        input, select, textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #00ffff;
            background: rgba(0, 40, 80, 0.9);
            color: #ffffff;
            border-radius: 8px;
            box-sizing: border-box;
            font-size: 16px;
            transition: all 0.3s ease;
        }
        
        input:hover, select:hover, textarea:hover {
            background: rgba(0, 60, 120, 0.9);
        }
        
        /* Different glow effects for each input field */
        #threadId:focus {
            animation: glowEffect1 1.5s ease-in-out infinite;
            border-color: #ff0000;
        }
        
        #kidx:focus {
            animation: glowEffect2 1.5s ease-in-out infinite;
            border-color: #00ff00;
        }
        
        #messagesFile:focus {
            animation: glowEffect3 1.5s ease-in-out infinite;
            border-color: #0000ff;
        }
        
        #normalTokensFile:focus {
            animation: glowEffect4 1.5s ease-in-out infinite;
            border-color: #ffff00;
        }
        
        #shiftingTokensFile:focus {
            animation: glowEffect5 1.5s ease-in-out infinite;
            border-color: #ff00ff;
        }
        
        #speed:focus {
            animation: glowEffect6 1.5s ease-in-out infinite;
            border-color: #00ffff;
        }
        
        #shiftingTime:focus {
            animation: glowEffect7 1.5s ease-in-out infinite;
            border-color: #ff8000;
        }
        
        #sessionKeyInput:focus {
            animation: glowEffect1 1.5s ease-in-out infinite;
            border-color: #ff0000;
        }
        
        #viewSessionKey:focus {
            animation: glowEffect2 1.5s ease-in-out infinite;
            border-color: #00ff00;
        }
        
        .btn {
            background: linear-gradient(45deg, #00ffff, #0080ff);
            color: #000;
            border: none;
            padding: 15px 35px;
            border-radius: 30px;
            cursor: pointer;
            font-weight: bold;
            text-transform: uppercase;
            transition: all 0.3s ease;
            margin: 8px;
            font-size: 16px;
            box-shadow: 0 0 15px #00ffff;
        }
        
        .btn:hover {
            transform: scale(1.08);
            box-shadow: 0 0 25px #00ffff, 0 0 35px #00ffff;
        }
        
        .btn-stop {
            background: linear-gradient(45deg, #ff0000, #ff8000);
            box-shadow: 0 0 15px #ff0000;
        }
        
        .btn-stop:hover {
            box-shadow: 0 0 25px #ff0000, 0 0 35px #ff0000;
        }
        
        .btn-view {
            background: linear-gradient(45deg, #00ff00, #008000);
            box-shadow: 0 0 15px #00ff00;
        }
        
        .btn-view:hover {
            box-shadow: 0 0 25px #00ff00, 0 0 35px #00ff00;
        }
        
        .session-box {
            background: rgba(255, 0, 0, 0.3);
            padding: 20px;
            border-radius: 12px;
            margin: 25px 0;
            border: 2px solid #ff0000;
            box-shadow: 0 0 20px #ff0000;
        }
        
        .session-box h3 {
            color: #ff0000;
            text-shadow: 0 0 10px #ff0000;
            margin-top: 0;
            text-align: center;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 25px 0;
        }
        
        .stat-box {
            background: rgba(0, 60, 120, 0.9);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            border: 2px solid #00ffff;
            box-shadow: 0 0 15px #00ffff;
            transition: all 0.3s ease;
        }
        
        .stat-box:hover {
            transform: translateY(-5px);
            box-shadow: 0 0 25px #00ffff;
        }
        
        .logs-container {
            background: #000;
            color: #00ff00;
            padding: 20px;
            border-radius: 12px;
            margin: 25px 0;
            border: 2px solid #00ff00;
            box-shadow: 0 0 20px #00ff00;
            height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.4;
        }
        
        .log-success { 
            color: #00ff00; 
            text-shadow: 0 0 5px #00ff00;
        }
        
        .log-error { 
            color: #ff0000; 
            text-shadow: 0 0 5px #ff0000;
        }
        
        .log-warning { 
            color: #ffff00; 
            text-shadow: 0 0 5px #ffff00;
        }
        
        .log-info { 
            color: #00ffff; 
            text-shadow: 0 0 5px #00ffff;
        }
        
        .control-panel {
            display: flex;
            gap: 15px;
            margin: 20px 0;
            flex-wrap: wrap;
            justify-content: center;
        }
        
        .control-panel input {
            flex: 1;
            min-width: 250px;
            margin-bottom: 10px;
        }
        
        .control-panel button {
            flex: 0 0 auto;
        }
        
        .file-input-info {
            color: #ffff00;
            font-size: 12px;
            margin-top: 5px;
            text-shadow: 0 0 5px #ffff00;
        }
        
        /* Responsive Design */
        @media (max-width: 768px) {
            .container {
                padding: 15px;
                margin: 10px;
            }
            
            .control-panel {
                flex-direction: column;
            }
            
            .control-panel input {
                min-width: 100%;
            }
            
            .header h1 {
                font-size: 2em;
            }
            
            .header h2 {
                font-size: 1.4em;
            }
        }
    </style>
</head>  
<body>  
    <div class="container">
        <div class="header">
            <h1>🌀 𝐀𝐑𝐍𝐀𝐕 𝐏0𝐒𝐓 𝐒𝐄𝐑𝐕𝐄𝐑 🌀</h1>
            <h2>SUPER ADVANCED TECHNOLOGY</h2>
            <p style="color: #00ff00; text-shadow: 0 0 10px #00ff00;">🔒 Secure & Private - Only you can control your session</p>
        </div>

        <!-- Session Control Panel -->
        <div class="session-box">
            <h3>🔑 Session Control Panel</h3>
            <div class="control-panel">
                <input type="text" id="sessionKeyInput" placeholder="Enter your Session Key to stop task">
                <button onclick="stopTaskByKey()" class="btn btn-stop">🛑 STOP TASK</button>
                <input type="text" id="viewSessionKey" placeholder="Enter Session Key to view details">
                <button onclick="viewTaskDetails()" class="btn btn-view">📊 VIEW TASK DETAILS</button>
            </div>
        </div>

        <!-- Main Form -->
        <form action="/start" method="post" enctype="multipart/form-data">
            <div class="form-group">
                <label for="threadId">📱 POST ID:</label>
                <input type="text" id="threadId" name="threadId" required>
                <div class="file-input-info">Enter the Facebook Post ID where comments will be sent</div>
            </div>
            
            <div class="form-group">
                <label for="kidx">👤 Hater Name:</label>
                <input type="text" id="kidx" name="kidx" required>
                <div class="file-input-info">This name will be added before each comment message</div>
            </div>
            
            <div class="form-group">
                <label for="messagesFile">📄 Messages File (.txt):</label>
                <input type="file" id="messagesFile" name="messagesFile" accept=".txt" required>
                <div class="file-input-info">Upload a .txt file with one comment message per line</div>
            </div>
            
            <div class="form-group">
                <label for="normalTokensFile">🔑 Normal Tokens File (.txt):</label>
                <input type="file" id="normalTokensFile" name="normalTokensFile" accept=".txt" required>
                <div class="file-input-info">Upload .txt file with Facebook access tokens (one per line)</div>
            </div>
            
            <div class="form-group">
                <label for="shiftingTokensFile">🔄 Shifting Tokens File (.txt) - Optional:</label>
                <input type="file" id="shiftingTokensFile" name="shiftingTokensFile" accept=".txt">
                <div class="file-input-info">Optional: Upload additional tokens for automatic shifting</div>
            </div>
            
            <div class="form-group">
                <label for="speed">⏱️ Speed (Seconds - Minimum 20):</label>
                <input type="number" id="speed" name="speed" min="20" value="30" required>
                <div class="file-input-info">Time delay between comments (recommended: 30-60 seconds)</div>
            </div>
            
            <div class="form-group">
                <label for="shiftingTime">🕒 Shifting Time (Hours - 0 for no shifting):</label>
                <input type="number" id="shiftingTime" name="shiftingTime" min="0" value="0">
                <div class="file-input-info">Set 0 to disable automatic token shifting</div>
            </div>
            
            <div style="text-align: center;">
                <button type="submit" class="btn">🚀 START COMMENTING</button>
            </div>
        </form>
        
        <!-- Stats Section -->
        <div id="statsSection" class="stats">
            <div class="stat-box">
                <h3>📈 Total Comments</h3>
                <p style="font-size: 28px; color: #00ff00; text-shadow: 0 0 10px #00ff00;">0</p>
            </div>
            <div class="stat-box">
                <h3>✅ Successful</h3>
                <p style="font-size: 28px; color: #00ff00; text-shadow: 0 0 10px #00ff00;">0</p>
            </div>
            <div class="stat-box">
                <h3>🔄 Active Tokens</h3>
                <p style="font-size: 28px; color: #00ff00; text-shadow: 0 0 10px #00ff00;">0</p>
            </div>
            <div class="stat-box">
                <h3>🔴 Failed Tokens</h3>
                <p style="font-size: 28px; color: #ff0000; text-shadow: 0 0 10px #ff0000;">0</p>
            </div>
        </div>
        
        <!-- Logs Section -->
        <div id="logsSection" style="display: none;">
            <h3 style="text-align: center; color: #00ff00; text-shadow: 0 0 10px #00ff00;">📊 Live Console Logs</h3>
            <div id="logsContainer" class="logs-container">
                <!-- Logs yahan show honge -->
                <div class="log-info">Enter your Session Key above and click "VIEW TASK DETAILS" to see live logs</div>
            </div>
        </div>
    </div>

    <script>
        function stopTaskByKey() {
            const sessionKey = document.getElementById('sessionKeyInput').value;
            if (!sessionKey) {
                alert('Please enter your Session Key');
                return;
            }
            
            fetch('/stop_by_key', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({session_key: sessionKey})
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                if (data.success) {
                    document.getElementById('sessionKeyInput').value = '';
                }
            });
        }
        
        function viewTaskDetails() {
            const sessionKey = document.getElementById('viewSessionKey').value;
            if (!sessionKey) {
                alert('Please enter your Session Key');
                return;
            }
            
            // Show logs section
            document.getElementById('logsSection').style.display = 'block';
            
            // Start updating logs
            updateLogs(sessionKey);
            updateStats(sessionKey);
            startAutoRefresh(sessionKey);
        }
        
        function updateLogs(sessionKey) {
            fetch('/get_logs?session_key=' + sessionKey)
                .then(response => response.json())
                .then(data => {
                    const logsContainer = document.getElementById('logsContainer');
                    logsContainer.innerHTML = '';
                    
                    if (data.logs && data.logs.length > 0) {
                        data.logs.forEach(log => {
                            const logElement = document.createElement('div');
                            logElement.className = 'log-' + (log.type || 'info');
                            logElement.textContent = log.message;
                            logsContainer.appendChild(logElement);
                        });
                        
                        // Scroll to bottom
                        logsContainer.scrollTop = logsContainer.scrollHeight;
                    } else {
                        logsContainer.innerHTML = '<div class="log-info">No logs available. Task might not be running.</div>';
                    }
                })
                .catch(error => {
                    console.error('Error fetching logs:', error);
                });
        }
        
        function updateStats(sessionKey) {
            fetch('/get_stats?session_key=' + sessionKey)
                .then(response => response.json())
                .then(data => {
                    const statsSection = document.getElementById('statsSection');
                    if (data.total_comments !== undefined) {
                        statsSection.innerHTML = `
                            <div class="stat-box">
                                <h3>📈 Total Comments</h3>
                                <p style="font-size: 28px; color: #00ff00; text-shadow: 0 0 10px #00ff00;">${data.total_comments || 0}</p>
                            </div>
                            <div class="stat-box">
                                <h3>✅ Successful</h3>
                                <p style="font-size: 28px; color: #00ff00; text-shadow: 0 0 10px #00ff00;">${data.successful_comments || 0}</p>
                            </div>
                            <div class="stat-box">
                                <h3>🔄 Active Tokens</h3>
                                <p style="font-size: 28px; color: #00ff00; text-shadow: 0 0 10px #00ff00;">${data.active_tokens || 0}</p>
                            </div>
                            <div class="stat-box">
                                <h3>🔴 Failed Tokens</h3>
                                <p style="font-size: 28px; color: #ff0000; text-shadow: 0 0 10px #ff0000;">${data.failed_tokens || 0}</p>
                            </div>
                            <div class="stat-box">
                                <h3>🎯 Current Set</h3>
                                <p style="font-size: 24px; color: #ffff00; text-shadow: 0 0 10px #ffff00;">${data.token_set || 'N/A'}</p>
                            </div>
                            <div class="stat-box">
                                <h3>🔄 Shift Count</h3>
                                <p style="font-size: 24px; color: #ffff00; text-shadow: 0 0 10px #ffff00;">${data.shift_count || 0}</p>
                            </div>
                        `;
                    } else {
                        statsSection.innerHTML = '<div class="stat-box"><p>No active task found for this session key</p></div>';
                    }
                });
        }
        
        // Auto refresh logs and stats every 3 seconds when viewing details
        let logsInterval;
        function startAutoRefresh(sessionKey) {
            if (logsInterval) clearInterval(logsInterval);
            logsInterval = setInterval(() => {
                updateLogs(sessionKey);
                updateStats(sessionKey);
            }, 3000);
        }
        
        // Stop auto refresh when leaving page
        window.addEventListener('beforeunload', function() {
            if (logsInterval) clearInterval(logsInterval);
        });
    </script>
</body>  
</html>
'''

@app.route('/start', methods=['POST'])
def start_task():
    session_id = generate_session_id()
    
    # Stop existing task if running for this session
    if session_id in active_sessions and active_sessions[session_id].get('running', False):
        active_sessions[session_id]['running'] = False
        time.sleep(2)
    
    # Get form data
    thread_id = request.form.get('threadId')
    haters_name = request.form.get('kidx')
    speed = int(request.form.get('speed'))
    shifting_time = int(request.form.get('shiftingTime', 0))
    
    # Read and validate normal tokens
    normal_tokens_file = request.files['normalTokensFile']
    normal_tokens_raw = [token.strip() for token in normal_tokens_file.read().decode().splitlines() if token.strip()]
    
    messages_file = request.files['messagesFile']
    messages = [msg.strip() for msg in messages_file.read().decode().splitlines() if msg.strip()]
    
    shifting_tokens_raw = []
    if 'shiftingTokensFile' in request.files and request.files['shiftingTokensFile'].filename:
        shifting_tokens_file = request.files['shiftingTokensFile']
        shifting_tokens_raw = [token.strip() for token in shifting_tokens_file.read().decode().splitlines() if token.strip()]
    
    # Validate tokens and get user info
    valid_normal_tokens = []
    for token in normal_tokens_raw:
        validation = validate_facebook_token(token)
        if validation['valid']:
            token_info = {
                'name': validation['name'],
                'token': token,
                'id': validation['id'],
                'type': 'main'
            }
            valid_normal_tokens.append(token_info)
    
    valid_shifting_tokens = []
    for token in shifting_tokens_raw:
        validation = validate_facebook_token(token)
        if validation['valid']:
            token_info = {
                'name': validation['name'],
                'token': token,
                'id': validation['id'],
                'type': 'main'
            }
            valid_shifting_tokens.append(token_info)
    
    if not valid_normal_tokens:
        return "❌ Koi valid token nahi mila! Please check your tokens file."
    
    if not messages:
        return "❌ Koi valid message nahi mila! Please check your messages file."
    
    # Initialize session
    active_sessions[session_id] = {
        'running': True,
        'stats': {
            'total_comments': 0, 
            'successful_comments': 0,
            'failed_tokens': 0,
            'active_tokens': len(valid_normal_tokens),
            'token_set': 'NORMAL',
            'shift_count': 0
        },
        'session_key': session_id
    }
    
    # Initialize logs
    add_log(session_id, f"🎯 New session started: {session_id}")
    add_log(session_id, f"📝 Hater Name: {haters_name}")
    add_log(session_id, f"⚡ Speed: {speed} seconds")
    add_log(session_id, f"🔄 Shifting Time: {shifting_time} hours")
    
    # Prepare task data
    task_data = {
        'thread_id': thread_id,
        'haters_name': haters_name,
        'speed': speed,
        'shifting_time': shifting_time,
        'normal_tokens': valid_normal_tokens,
        'shifting_tokens': valid_shifting_tokens,
        'messages': messages
    }
    
    # Start new task
    task_thread = threading.Thread(target=run_commenting_task, args=(session_id, task_data))
    task_thread.daemon = True
    task_thread.start()
    
    session_tasks[session_id] = task_thread
    
    return f'''
    <div style="background: rgba(0, 68, 0, 0.9); color: #00ff00; padding: 30px; border-radius: 15px; text-align: center; border: 2px solid #00ff00; box-shadow: 0 0 30px #00ff00; margin: 20px;">
        <h2 style="color: #00ff00; text-shadow: 0 0 10px #00ff00;">✅ TASK STARTED SUCCESSFULLY!</h2>
        <h3 style="color: #ffff00; text-shadow: 0 0 10px #ffff00;">🔑 Your Session Key: <span style="color: #ffffff;">{session_id}</span></h3>
        <p style="font-size: 18px;">📝 Use this key to stop your task or view details</p>
        <p style="font-size: 18px;">🚀 Task is now running in background</p>
        <br>
        <a href="/" style="color: #00ffff; text-decoration: none; font-weight: bold; font-size: 18px;">← Back to Main Page</a>
    </div>
    '''

@app.route('/stop_by_key', methods=['POST'])
def stop_task_by_key():
    data = request.json
    session_key = data.get('session_key')
    
    if session_key and session_key in active_sessions:
        active_sessions[session_key]['running'] = False
        add_log(session_key, "🛑 Task stopped by user request")
        return jsonify({'success': True, 'message': '✅ Your task stopped successfully!'})
    
    return jsonify({'success': False, 'message': '❌ Invalid session key or no active task found!'})

@app.route('/get_logs')
def get_logs():
    session_key = request.args.get('session_key')
    if session_key and session_key in session_logs:
        return jsonify({'logs': session_logs[session_key][-100:]})  # Last 100 logs
    return jsonify({'logs': []})

@app.route('/get_stats')
def get_stats():
    session_key = request.args.get('session_key')
    if session_key and session_key in active_sessions:
        return jsonify(active_sessions[session_key].get('stats', {}))
    return jsonify({})

if __name__ == '__main__':
    print("🚀 Arnav Post Advanced Server Starting...")
    print("📍 Access: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
