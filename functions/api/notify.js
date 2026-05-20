// functions/api/notify.js
// Free SMS via Verizon email-to-text gateway (no Twilio needed)

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    const { order_id, total } = await request.json();

    if (!order_id || !total) {
      return new Response(
        JSON.stringify({ success: false, error: "Missing order_id or total" }),
        { status: 400, headers: corsHeaders }
      );
    }

    // Keith's Verizon number — email-to-text gateway (free, no account needed)
    const keithSMS = "3184231053@vtext.com";

    // EmailJS credentials from environment variables
    const emailjsServiceId  = env.EMAILJS_SERVICE_ID;
    const emailjsTemplateId = env.EMAILJS_TEMPLATE_ID;
    const emailjsPublicKey  = env.EMAILJS_PUBLIC_KEY;

    if (!emailjsServiceId || !emailjsTemplateId || !emailjsPublicKey) {
      return new Response(
        JSON.stringify({ success: false, error: "EmailJS credentials not configured" }),
        { status: 500, headers: corsHeaders }
      );
    }

    const emailPayload = {
      service_id:  emailjsServiceId,
      template_id: emailjsTemplateId,
      user_id:     emailjsPublicKey,
      template_params: {
        to_email: keithSMS,
        subject:  "New Honey Order",
        message:  `New order! ID: ${order_id} — Total: $${total}. Check dashboard.`,
      },
    };

    const emailRes = await fetch("https://api.emailjs.com/api/v1.0/email/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(emailPayload),
    });

    if (!emailRes.ok) {
      const errText = await emailRes.text();
      return new Response(
        JSON.stringify({ success: false, error: "EmailJS error", details: errText }),
        { status: 502, headers: corsHeaders }
      );
    }

    return new Response(
      JSON.stringify({ success: true, message: "SMS sent via Verizon gateway" }),
      { status: 200, headers: corsHeaders }
    );

  } catch (err) {
    return new Response(
      JSON.stringify({ success: false, error: err.message }),
      { status: 500, headers: corsHeaders }
    );
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: corsHeaders,
  });
}
