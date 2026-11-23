// Exercise the packaged UI in the same system WebKit used by the macOS desktop.
import AppKit
import WebKit

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let page = WKWebView(frame: NSRect(x: 0, y: 0, width: 1100, height: 760))
let check = """
const menu = document.querySelector('[data-testid="taobao-menu"]');
if (!menu) return false;
const trigger = menu.querySelector('summary');
function requireState(open) {
    if (menu.open !== open) throw new Error('Unexpected store menu state: ' + menu.open);
}
trigger.click();
requireState(true);
document.querySelector('h1').click();
requireState(false);
trigger.click();
const link = menu.querySelector('a');
link.addEventListener('click', e => e.preventDefault(), {once: true});
link.click();
requireState(false);
trigger.click();
link.focus();
link.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
requireState(false);
if (document.activeElement !== trigger) throw new Error('Escape did not restore focus');
return true;
"""

final class MenuTest: NSObject, WKNavigationDelegate {
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        checkMenu()
    }
    func checkMenu() {
        page.callAsyncJavaScript(check, arguments: [:], in: nil, in: .page) { result in
            switch result {
            case .success(let value):
                if value as? Bool == true { exit(0) }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { self.checkMenu() }
            case .failure(let error):
                FileHandle.standardError.write(Data("WebKit menu test: \(error)\n".utf8))
                exit(1)
            }
        }
    }
}
let test = MenuTest()
page.navigationDelegate = test
let window = NSWindow(contentRect: page.frame, styleMask: [.titled], backing: .buffered, defer: false)
window.contentView = page
window.orderFront(nil)
page.load(URLRequest(url: URL(string: CommandLine.arguments[1])!))
DispatchQueue.main.asyncAfter(deadline: .now() + 60) { exit(2) }
app.run()
