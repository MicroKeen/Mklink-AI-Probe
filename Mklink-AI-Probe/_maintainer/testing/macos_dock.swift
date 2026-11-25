// Drive the installed app's red close button and menu-bar item through public Accessibility APIs.
import AppKit
import ApplicationServices

guard AXIsProcessTrusted() else {
    print("macOS Dock interaction unavailable: test runner lacks Accessibility permission")
    exit(77)
}

struct CheckError: Error { let message: String }

func attribute(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success ? value : nil
}

func element(_ parent: AXUIElement, _ name: String) -> AXUIElement? {
    guard let value = attribute(parent, name), CFGetTypeID(value) == AXUIElementGetTypeID() else { return nil }
    return (value as! AXUIElement)
}

func waitFor<T>(_ description: String, _ read: () -> T?) throws -> T {
    let end = Date().addingTimeInterval(15)
    repeat {
        if let value = read() { return value }
        RunLoop.current.run(until: Date().addingTimeInterval(0.1))
    } while Date() < end
    throw CheckError(message: description)
}

func press(_ item: AXUIElement) throws {
    let result = AXUIElementPerformAction(item, kAXPressAction as CFString)
    // AppKit can enter menu tracking before the Accessibility reply returns.
    guard result == .success || result == .cannotComplete else {
        throw CheckError(message: "AXPress failed: \(result.rawValue)")
    }
}

func check(_ pid: pid_t) throws {
    let app = AXUIElementCreateApplication(pid)
    func windows() -> [AXUIElement] { attribute(app, kAXWindowsAttribute) as? [AXUIElement] ?? [] }
    func visibleMainWindows() -> [Int] {
        let entries = CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID) as? [[String: Any]] ?? []
        return entries.compactMap { entry in
            guard entry[kCGWindowOwnerPID as String] as? Int == Int(pid),
                  entry[kCGWindowLayer as String] as? Int == 0,
                  let bounds = entry[kCGWindowBounds as String] as? [String: Any],
                  (bounds["Width"] as? Double ?? 0) >= 800 else { return nil }
            return entry[kCGWindowNumber as String] as? Int
        }
    }
    func policy() -> NSApplication.ActivationPolicy? {
        NSRunningApplication(processIdentifier: pid)?.activationPolicy
    }
    let window = try waitFor("foreground main window") {
        policy() == .regular ? windows().first(where: { attribute($0, kAXTitleAttribute) as? String == "Mklink AI Probe" }) : nil
    }
    let close = try waitFor("main window close button") { element(window, kAXCloseButtonAttribute) }
    let number = try waitFor("visible main window number") { visibleMainWindows().first }
    try press(close)
    _ = try waitFor("closed window with accessory activation policy") {
        policy() == .accessory && !visibleMainWindows().contains(number) ? true : nil
    }
    let item = try waitFor("MKLink menu-bar status item") { () -> AXUIElement? in
        guard let bar = element(app, kAXExtrasMenuBarAttribute) else { return nil }
        return (attribute(bar, kAXChildrenAttribute) as? [AXUIElement])?.first
    }
    try press(item)
    let show = try waitFor("Show MKLink menu action") { () -> AXUIElement? in
        let children = attribute(item, kAXChildrenAttribute) as? [AXUIElement] ?? []
        for menu in children {
            let actions = attribute(menu, kAXChildrenAttribute) as? [AXUIElement] ?? []
            if let action = actions.first(where: { attribute($0, kAXTitleAttribute) as? String == "Show MKLink" }) {
                return action
            }
        }
        return nil
    }
    try press(show)
    _ = try waitFor("restored main window and regular activation policy on the same PID") {
        policy() == .regular && visibleMainWindows().contains(number) ? true : nil
    }
}

func run() throws {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: CommandLine.arguments[1])
    try process.run()
    defer {
        if process.isRunning {
            _ = NSRunningApplication(processIdentifier: process.processIdentifier)?.terminate()
            if (try? waitFor("desktop quit", { !process.isRunning ? true : nil })) == nil && process.isRunning {
                process.terminate()
            }
        }
    }
    try check(process.processIdentifier)
}

do {
    try run()
} catch {
    FileHandle.standardError.write(Data("macOS Dock check: \(error)\n".utf8))
    exit(1)
}
