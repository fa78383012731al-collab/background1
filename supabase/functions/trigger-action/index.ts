import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const GITHUB_TOKEN  = Deno.env.get("GITHUB_TOKEN")!;
const GITHUB_OWNER  = "fa78383012731al-collab";
const GITHUB_REPO   = "background1";
const WORKFLOW_FILE = "process-pptx.yml";

const corsHeaders = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { job_id, file_path } = await req.json();
    if (!job_id || !file_path) {
      return new Response(
        JSON.stringify({ error: "job_id and file_path are required" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Trigger GitHub Actions workflow_dispatch
    const ghUrl = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`;
    const r = await fetch(ghUrl, {
      method: "POST",
      headers: {
        "Authorization": `token ${GITHUB_TOKEN}`,
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
        "User-Agent":    "PPTX-Reconstructor/1.0",
      },
      body: JSON.stringify({
        ref: "main",
        inputs: {
          job_id:    job_id,
          file_path: file_path,
        },
      }),
    });

    if (r.status === 204) {
      return new Response(
        JSON.stringify({ success: true, message: "GitHub Actions triggered" }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const body = await r.text();
    return new Response(
      JSON.stringify({ error: `GitHub API error ${r.status}: ${body}` }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
