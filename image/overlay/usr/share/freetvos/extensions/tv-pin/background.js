/*
 * The only part of the pin extension that can reach the helper on the box.
 *
 * A content script cannot start a native helper; this service worker can, and
 * it adds the one thing the page must not choose: the address. It comes from
 * Chromium's record of which page sent the message, not from the message, so a
 * page cannot ask to pin somewhere it is not.
 */
var HELPER = "org.freetvos.pin";

chrome.runtime.onMessage.addListener(function (msg, sender, reply) {
  if (sender.id !== chrome.runtime.id || !sender.tab || sender.frameId !== 0) {
    return false;
  }
  var op = msg && msg.op;
  if (op !== "status" && op !== "pin" && op !== "unpin") return false;

  var request = {
    op: op,
    url: sender.url || "",
    name: typeof msg.name === "string" ? msg.name.slice(0, 200) : "",
    image: typeof msg.image === "string" ? msg.image.slice(0, 2000) : ""
  };
  chrome.runtime.sendNativeMessage(HELPER, request, function (response) {
    if (chrome.runtime.lastError || !response) {
      reply({ ok: false, error: "The pinning helper did not answer." });
      return;
    }
    reply(response);
  });
  return true;   // the reply comes later
});
