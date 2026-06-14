# PPTX Diagram Reconstructor

تطبيق ويب احترافي يحلّل ملفات PowerPoint ويعيد بناء المخططات كعناصر قابلة للتعديل بالكامل.

## المميزات

- واجهة ويب HTML/CSS/JS نظيفة ومتجاوبة
- رفع ملفات PPTX وتحليل الشرائح تلقائيًا
- اكتشاف المخططات والانفوجرافيك والـ flowcharts
- إعادة بناء المخططات كـ editable PowerPoint shapes
- OCR للنصوص العربية والإنجليزية داخل الصور
- تصدير PPTX جديد + SVG + PNG
- رفع النتائج إلى GitHub مباشرة

## التثبيت والتشغيل

```bash
git clone https://github.com/fa78383012731al-collab/background1
cd background1
pip install -r requirements.txt
python server.py
```

افتح المتصفح على: http://localhost:8000

## Docker

```bash
docker build -t pptx-reconstructor .
docker run -p 8000:8000 -e GITHUB_TOKEN=your_token pptx-reconstructor
```

## هيكل المشروع

```
├── static/
│   ├── index.html      ← واجهة المستخدم
│   ├── styles.css      ← التصميم
│   └── app.js          ← منطق الواجهة
├── server.py           ← Flask API server
├── processor.py        ← تحليل PPTX واكتشاف المخططات
├── rebuild_diagram.py  ← إعادة بناء الأشكال القابلة للتعديل
├── export_svg.py       ← تصدير SVG
├── export_png.py       ← تصدير PNG عالي الدقة
├── github_push.py      ← رفع إلى GitHub
├── requirements.txt
├── Dockerfile
└── tests/
```

## متغيرات البيئة

| المتغير | الغرض |
|---|---|
| `GITHUB_TOKEN` | Personal Access Token لـ GitHub |
| `PORT` | رقم المنفذ (افتراضي: 8000) |

## API Endpoints

| Method | Path | الوصف |
|---|---|---|
| POST | `/api/upload` | رفع ملف PPTX |
| POST | `/api/process/:id` | بدء التحليل |
| GET  | `/api/status/:id` | حالة المعالجة |
| GET  | `/api/download/:file` | تنزيل ملف |
| POST | `/api/github-push/:id` | رفع إلى GitHub |

## License

MIT
