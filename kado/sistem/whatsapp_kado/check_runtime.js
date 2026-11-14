'use strict';
require('whatsapp-web.js');
require('qrcode-terminal');
const fs = require('fs');
const executable = require('ffmpeg-static');
if (!executable || !fs.existsSync(executable)) throw new Error('FFmpeg bulunamadi. Kurulumu tekrar deneyin.');
const puppeteer = require('puppeteer');
if (!fs.existsSync(puppeteer.executablePath())) throw new Error('Chromium indirilemedi. Kurulumu tekrar deneyin.');
console.log('WhatsApp, Chromium ve FFmpeg hazir.');
