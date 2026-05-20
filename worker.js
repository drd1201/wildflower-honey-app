import notifyHandler from "./functions/api/notify.js";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    if (url.pathname === "/api/notify") {
      return notifyHandler.fetch(request, env, ctx);
    }

    // Serve static files for everything else
    return fetch(request);
  }
};
