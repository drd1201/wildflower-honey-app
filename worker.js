export default {
  async fetch(request, env, ctx) {
    return new Response(null, { status: 404 });
  }
};
