const express = require('express');
const WebSocket = require('ws');
const http = require('http');
const path = require('path');
const fs = require('fs');

// 读取配置文件
const config = JSON.parse(fs.readFileSync('config.json', 'utf8'));
const PORT = config.port;
const IP = config.ip;

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

// 存储数据
let currentAnnouncement = '';
let feedbacks = [];
const clients = new Set();

// 静态文件
app.use(express.static(__dirname));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// WebSocket连接
wss.on('connection', (ws) => {
    console.log('用户端已连接，当前在线:', clients.size + 1);
    clients.add(ws);
    
    // 发送当前公告
    ws.send(JSON.stringify({
        type: 'announcement',
        data: currentAnnouncement,
        timestamp: new Date().toISOString()
    }));
    
    ws.on('close', () => {
        clients.delete(ws);
        console.log('用户端断开，当前在线:', clients.size);
    });
});

// 广播公告
function broadcast(data) {
    const message = JSON.stringify(data);
    clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(message);
        }
    });
}

// API: 发布公告
app.post('/api/announcement', (req, res) => {
    const { content } = req.body;
    if (content && content.trim()) {
        currentAnnouncement = content;
        broadcast({
            type: 'announcement',
            data: currentAnnouncement,
            timestamp: new Date().toISOString()
        });
        res.json({ success: true, message: '公告已发布' });
    } else {
        res.json({ success: false, message: '内容不能为空' });
    }
});

// API: 获取当前公告
app.get('/api/announcement', (req, res) => {
    res.json({
        success: true,
        data: currentAnnouncement,
        timestamp: new Date().toISOString()
    });
});

// API: 提交反馈
app.post('/api/feedback', (req, res) => {
    const { content } = req.body;
    if (content && content.trim()) {
        const feedback = {
            id: feedbacks.length + 1,
            content: content,
            timestamp: new Date().toISOString()
        };
        feedbacks.push(feedback);
        res.json({ success: true, message: '反馈已提交' });
    } else {
        res.json({ success: false, message: '内容不能为空' });
    }
});

// API: 获取所有反馈
app.get('/api/feedbacks', (req, res) => {
    res.json({ success: true, data: feedbacks });
});

// API: 清空公告
app.delete('/api/announcement', (req, res) => {
    currentAnnouncement = '';
    broadcast({
        type: 'announcement',
        data: '',
        timestamp: new Date().toISOString()
    });
    res.json({ success: true, message: '公告已清空' });
});

// API: 获取在线客户端数量
app.get('/api/clients', (req, res) => {
    res.json({ success: true, count: clients.size });
});

// 主页 - 直接显示owner.html
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'owner.html'));
});

// 启动服务器
server.listen(PORT, IP, () => {
    console.log(`\n========================================`);
    console.log(`✅ 公告系统服务器已启动`);
    console.log(`========================================`);
    console.log(`📍 本地访问: http://127.0.0.1:${PORT}`);
    console.log(`📍 局域网访问: http://${getLocalIp()}:${PORT}`);
    console.log(`========================================\n`);
});

// 获取本机局域网IP
function getLocalIp() {
    const { networkInterfaces } = require('os');
    const nets = networkInterfaces();
    for (const name of Object.keys(nets)) {
        for (const net of nets[name]) {
            if (net.family === 'IPv4' && !net.internal) {
                return net.address;
            }
        }
    }
    return '127.0.0.1';
}