/* SmartBox loopback Rime session transport. A queue includes each DOM continuation. */
(function () {
  "use strict";

  function RimeClient() {
    var url = new URL("/api/ime", window.location.href);
    url.protocol = "http:";
    url.port = "8080";
    this.base = url.href.replace(/\/$/, "");
    this.generation = 0;
    this.session = null;
    this.snapshot = null;
    this.failure = null;
    this.queue = Promise.resolve();
  }

  RimeClient.prototype.request = async function (path, method, body) {
    var options = { method: method, credentials: "omit" };
    if (body !== undefined) {
      options.headers = { "Content-Type": "application/json" };
      options.body = JSON.stringify(body);
    }
    var response = await window.fetch(this.base + path, options);
    if (!response.ok) throw new Error("Rime request failed (" + response.status + ")");
    return response.status === 204 ? null : response.json();
  };

  RimeClient.prototype.remove = function (id) {
    if (id) this.request("/sessions/" + encodeURIComponent(id), "DELETE").catch(function () {});
  };

  RimeClient.prototype.reset = function () {
    this.generation++;
    this.remove(this.session);
    this.session = this.snapshot = this.failure = null;
    this.queue = Promise.resolve();
  };

  // action may depend on the last authoritative snapshot (e.g. empty Backspace).
  // Store commits as drained so a local continuation never inserts them twice.
  RimeClient.prototype.run = function (action, continuation) {
    var self = this;
    var generation = this.generation;
    var work = this.queue.then(async function () {
      if (generation !== self.generation) return;
      if (self.failure) throw self.failure;
      try {
        if (!self.session) {
          var opened = await self.request("/sessions", "POST");
          if (generation !== self.generation) { self.remove(opened.session_id); return; }
          self.session = opened.session_id;
          self.snapshot = Object.assign({}, opened, { commit: "" });
        }
        var submitted = typeof action === "function" ? action(self.snapshot) : action;
        var result = submitted
          ? await self.request("/sessions/" + encodeURIComponent(self.session) + "/actions", "POST", submitted)
          : self.snapshot;
        if (generation !== self.generation) return;
        self.snapshot = Object.assign({}, result, { commit: "" });
        if (continuation) await continuation(result, submitted);
        return result;
      } catch (error) {
        if (generation === self.generation) self.failure = error;
        throw error;
      }
    });
    this.queue = work.catch(function () {});
    return work;
  };

  window.SmartBoxRimeClient = RimeClient;
})();
