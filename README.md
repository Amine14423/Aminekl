# ⚡ Cloud Run Fast Bot

بوت تيليغرام لنشر Google Cloud Run بأسرع وقت ممكن.

## 🚀 النشر على Railway

### 1. ارفع المستودع على GitHub
```bash
git init
git add .
git commit -m "first commit"
git remote add origin https://github.com/اسمك/اسم-المستودع.git
git push -u origin main
```

### 2. اربط Railway بـ GitHub
- اذهب إلى [railway.app](https://railway.app)
- New Project → Deploy from GitHub repo
- اختر المستودع

### 3. أضف المتغيرات في Railway
في Variables أضف:
```
TELEGRAM_TOKEN = توكن البوت
OWNER_ID       = 8372270954
```

### 4. شغّل! ✅

## 📋 الأوامر
- `/start` — الرئيسية
- `/help` — المساعدة  
- `/status` — حالة الخدمة
- `/regions` — المناطق
- `/cancel` — إلغاء
- `/stats` — إحصائيات (المالك فقط)
- `/lock` — قفل البوت (المالك فقط)
- `/unlock` — فتح البوت (المالك فقط)
