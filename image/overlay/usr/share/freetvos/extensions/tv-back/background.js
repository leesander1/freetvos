/*
 * Closes the window of the page that asked. A page cannot close a window it did
 * not open, and a service's window was opened by the launcher, so the page asks
 * here. It can only ever close its own window.
 */
chrome.runtime.onMessage.addListener(function (msg, sender) {
  if (!msg || msg.op !== "close") return;
  if (sender.id !== chrome.runtime.id || !sender.tab || sender.frameId !== 0) return;
  chrome.windows.remove(sender.tab.windowId);
});
