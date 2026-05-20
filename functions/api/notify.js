const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    try {
      const { order_id, total } = await request.json();

      if (!order_id || !total) {
        return new Response(
          JSON.stringify({ success: false, error: "Missing order_id or total" }),
          { status: 400, headers: corsHeaders }
        );
      }

      const emailPayload = {
        service_id:  env.EMAILJS_SERVICE_ID,
        template_id: env.EMAILJS_TEMPLATE_ID,
        user_id:     env.EMAILJS_PUBLIC_KEY,
        template_params: {
          to_email: "3184231053@vtext.com",
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
};
