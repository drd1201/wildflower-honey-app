export async function onRequestPost(context) {
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
  };

  try {
    const body = await context.request.json();
    const { order_id, total } = body;

    if (!order_id || total === undefined) {
      return new Response(
        JSON.stringify({ success: false, error: "Missing order_id or total" }),
        { status: 400, headers: corsHeaders }
      );
    }

    const env = context.env || {};
    const accountSid = env.TWILIO_ACCOUNT_SID;
    const authToken = env.TWILIO_AUTH_TOKEN;
    const fromNumber = env.TWILIO_FROM_NUMBER || "+18556838803";
    const toNumber = env.TWILIO_TO_NUMBER || "+13184231053";

    if (!accountSid || !authToken) {
      return new Response(
        JSON.stringify({ success: false, error: "Twilio credentials not configured" }),
        { status: 500, headers: corsHeaders }
      );
    }

    const messageBody = `\u{1F36F} New Honey Order! Order ID: ${order_id}, Total: $${total}. Check the dashboard for details.`;

    const twilioUrl = `https://api.twilio.com/2010-04-01/Accounts/${accountSid}/Messages.json`;

    const params = new URLSearchParams();
    params.append("To", toNumber);
    params.append("From", fromNumber);
    params.append("Body", messageBody);

    const authHeader = "Basic " + btoa(`${accountSid}:${authToken}`);

    const twilioResponse = await fetch(twilioUrl, {
      method: "POST",
      headers: {
        "Authorization": authHeader,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: params.toString(),
    });

    const twilioData = await twilioResponse.json();

    if (!twilioResponse.ok) {
      return new Response(
        JSON.stringify({
          success: false,
          error: "Twilio API error",
          details: twilioData.message || twilioData,
        }),
        { status: 502, headers: corsHeaders }
      );
    }

    return new Response(
      JSON.stringify({
        success: true,
        message_sid: twilioData.sid,
        status: twilioData.status,
      }),
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
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}
