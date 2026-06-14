# PPTX Diagram Reconstructor

تطبيق ويب **مجاني 100%** يحلّل ملفات PowerPoint ويعيد بناء المخططات كعناصر قابلة للتعديل.

## البنية التقنية — مجانية بالكامل

```
المستخدم (GitHub Pages)
    ↓ رفع PPTX
Supabase Storage (pptx-inputs)
    ↓ Edge Function تشغّل
GitHub Actions (Python مجاني)
    ↓ معالجة + إعادة بناء
Supabase Storage (pptx-outputs)
    ↓ روابط تنزيل مباشرة
GitHub Pages ← يعرض النتائج
```

## إعداد المشروع من الصفر

### 1. Supabase — إعداد قاعدة البيانات والتخزين

```sql
-- شغّل supabase/schema.sql في Supabase SQL Editor
```

### 2. Supabase — نشر Edge Function

```bash
npx supabase functions deploy trigger-action \
  --project-ref sdpjpgnwztqoncismayd

# أضف المتغيرات للـ Edge Function
npx supabase secrets set GITHUB_TOKEN=your_token \
  --project-ref sdpjpgnwztqoncismayd
```

### 3. GitHub — إضافة Secrets

في GitHub → Settings → Secrets → Actions أضف:

| المتغير | القيمة |
|---|---|
| `SUPABASE_URL` | `https://sdpjpgnwztqoncismayd.supabase.co` |
| `SUPABASE_SERVICE_KEY` | مفتاح service_role من Supabase |
| `SUPABASE_ANON_KEY` | مفتاح anon من Supabase |

### 4. GitHub Pages

في repo Settings → Pages → Source: **main branch / root**

الرابط: `https://fa78383012731al-collab.github.io/background1/`

## هيكل المشروع

```
├── index.html                          ← GitHub Pages entry
├── static/
│   ├── index.html                      ← Supabase-powered UI
│   ├── styles.css
│   └── app.js                          ← Upload → Supabase → poll status
├── .github/workflows/
│   └── process-pptx.yml               ← GitHub Actions pipeline
├── pipeline/
│   ├── download_input.py              ← Download from Supabase Storage
│   ├── run_pipeline.py                ← Process PPTX
│   └── upload_results.py             ← Upload results to Supabase
├── supabase/
│   ├── functions/trigger-action/      ← Edge Function (trigger Actions)
│   └── schema.sql                     ← DB + Storage setup
├── processor.py                        ← PPTX analysis
├── rebuild_diagram.py                  ← Vector shape reconstruction
├── export_svg.py / export_png.py
├── requirements.txt
└── Dockerfile
```

## تدفق العمل

1. المستخدم يرفع PPTX → **Supabase Storage**
2. JavaScript يُنشئ سجل وظيفة في **Supabase DB**
3. Edge Function تُشغّل **GitHub Actions** workflow
4. GitHub Actions يُنزّل PPTX، يُعالجه بـ Python، يرفع النتائج
5. الواجهة تُراقب حالة الوظيفة (polling كل 3 ثوانٍ)
6. عند الانتهاء: روابط تنزيل مباشرة من **Supabase Storage**

## License

MIT
