import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const GITHUB_TOKEN   = Deno.env.get("GITHUB_TOKEN")!;
const SUPABASE_URL   = Deno.env.get("SUPABASE_URL")   ?? "https://sdpjpgnwztqoncismayd.supabase.co";
const SUPABASE_KEY   = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? Deno.env.get("SUPABASE_KEY") ?? "";
const GITHUB_OWNER   = "fa78383012731al-collab";
const GITHUB_REPO    = "background1";
const WORKFLOW_FILE  = "process-pptx.yml";

const cors = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-job-id, x-filename",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  try {
    const ct = req.headers.get("content-type") ?? "";

    // ── Mode A: File upload (multipart) ──────────────────────────────────
    if (ct.includes("multipart/form-data")) {
      const form     = await req.formData();
      const file     = form.get("file") as File;
      const jobId    = form.get("job_id")   as string ?? crypto.randomUUID();
      const filename = form.get("filename") as string ?? file?.name ?? "upload.pptx";

      if (!file) return json({ error: "No file provided" }, 400);

      const filePath = `${jobId}/${filename}`;

      // Upload to Storage with service key
      const sbH = { "apikey": SUPABASE_KEY, "Authorization": `Bearer ${SUPABASE_KEY}` };

      const upR = await fetch(
        `${SUPABASE_URL}/storage/v1/object/pptx-inputs/${filePath}`,
        { method: "POST", headers: { ...sbH, "x-upsert": "true", "Content-Type": "application/octet-stream" }, body: file }
      );
      if (!upR.ok) {
        const e = await upR.text();
        return json({ error: `Storage upload failed: ${e}` }, 500);
      }

      // Create job record
      const jobR = await fetch(`${SUPABASE_URL}/rest/v1/jobs`, {
        method: "POST",
        headers: { ...sbH, "Content-Type": "application/json", "Prefer": "return=representation" },
        body: JSON.stringify({ id: jobId, status: "queued", progress: 10, filename, file_path: filePath, log: "Queued" }),
      });
      const jobs = await jobR.json();
      const job  = Array.isArray(jobs) ? jobs[0] : jobs;

      // Trigger GitHub Actions
      await triggerWorkflow(jobId, filePath);

      return json({ success: true, job_id: jobId, file_path: filePath, job });
    }

    // ── Mode B: JSON trigger only ────────────────────────────────────────
    const { job_id, file_path } = await req.json();
    if (!job_id || !file_path) return json({ error: "job_id and file_path required" }, 400);
    await triggerWorkflow(job_id, file_path);
    return json({ success: true });

  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});

async function triggerWorkflow(jobId: string, filePath: string) {
  const r = await fetch(
    `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
    {
      method: "POST",
      headers: {
        "Authorization": `token ${GITHUB_TOKEN}`,
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
        "User-Agent":    "PPTX-Bot/1.0",
      },
      body: JSON.stringify({ ref: "main", inputs: { job_id: jobId, file_path: filePath } }),
    }
  );
  if (r.status !== 204) throw new Error(`GitHub API ${r.status}: ${await r.text()}`);
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}
