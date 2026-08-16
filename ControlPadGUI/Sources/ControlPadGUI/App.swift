import SwiftUI

@main
struct ControlPadApp: App {
    @State private var appModel = AppModel()
    @AppStorage("appLanguage") private var languageRaw: String = AppLanguage.system.rawValue

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(appModel)
                // Cambiare lingua forza qui il rifacimento dell'intero
                // sottoalbero: L() legge da un Bundle statico, non da stato
                // osservato da SwiftUI, quindi senza questo le view già
                // disegnate non si aggiornerebbero da sole.
                .id(languageRaw)
                .task(id: languageRaw) {
                    L10n.apply(AppLanguage(rawValue: languageRaw) ?? .system)
                }
                .background(WindowFrameSaver(name: "ControlPadMainWindow"))
        }
        .defaultSize(width: 1180, height: 860)
        // .contentMinSize: la finestra può essere ingrandita quanto si vuole e
        // rimpicciolita fino al minimo del contenuto. Con il valore
        // predefinito il contenuto imponeva anche il massimo.
        .windowResizability(.contentMinSize)
    }
}

/// Ricorda posizione e dimensione della finestra fra un avvio e l'altro.
///
/// SwiftUI da solo non lo fa: `defaultSize` vale per la prima apertura e basta,
/// quindi ogni riavvio riportava la finestra alla misura di partenza. AppKit ha
/// già tutto (`setFrameAutosaveName` scrive in UserDefaults e ripristina), ma
/// bisogna arrivare alla NSWindow, che da SwiftUI si raggiunge solo passando
/// per una view rappresentabile.
private struct WindowFrameSaver: NSViewRepresentable {
    let name: String

    func makeNSView(context: Context) -> NSView {
        let view = NSView(frame: .zero)
        DispatchQueue.main.async {
            guard let window = view.window else { return }
            // Il nome va assegnato una volta sola: riassegnarlo a ogni
            // aggiornamento della view riscriverebbe il frame salvato con
            // quello corrente prima che il ripristino sia avvenuto.
            if window.frameAutosaveName != name {
                window.setFrameAutosaveName(name)
            }
        }
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {}
}
