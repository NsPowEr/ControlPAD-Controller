import Foundation

/// Gestisce il sottoprocesso ControlPadEngine/bridge.py: un comando JSON per
/// riga su stdin, una risposta JSON per riga su stdout. Il motore non viene
/// riscritto in Swift — questo attore è solo il trasporto.
actor PythonBridge {
    struct BridgeError: Error, LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    private var process: Process?
    private var stdin: FileHandle?
    private var nextID = 0
    private var pending: [Int: CheckedContinuation<JSONValue, Error>] = [:]
    private var readLoop: Task<Void, Never>?

    private let connectionStream: AsyncStream<Bool>
    private let connectionContinuation: AsyncStream<Bool>.Continuation

    /// Stato del pad (collegato/scollegato), come lo emette bridge.py col
    /// polling ogni 2s. La UI vi si abbona per mostrare/nascondere il banner.
    nonisolated var connectionEvents: AsyncStream<Bool> { connectionStream }

    init() {
        var continuation: AsyncStream<Bool>.Continuation!
        connectionStream = AsyncStream { continuation = $0 }
        connectionContinuation = continuation
    }

    func start() throws {
        guard process == nil else { return }

        let engineDir = Self.resolveEngineDirectory()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: Self.resolvePython3Path())
        process.arguments = ["-u", "bridge.py"]
        process.currentDirectoryURL = engineDir

        let stdinPipe = Pipe()
        let stdoutPipe = Pipe()
        process.standardInput = stdinPipe
        process.standardOutput = stdoutPipe
        // Lo stderr del motore finiva in /dev/null: se Python moriva all'avvio
        // (import mancante, errore di sintassi) l'app mostrava solo un pad che
        // non risponde, senza una riga da nessuna parte. Ora finisce nello
        // stesso file di log che si scrive il motore.
        process.standardError = Self.engineLogHandle() ?? FileHandle.nullDevice

        try process.run()

        self.process = process
        self.stdin = stdinPipe.fileHandleForWriting

        let stdoutHandle = stdoutPipe.fileHandleForReading
        readLoop = Task { [weak self] in
            guard let self else { return }
            do {
                for try await line in stdoutHandle.bytes.lines {
                    await self.handleLine(line)
                }
            } catch {
                // Pipe chiusa: il processo è terminato, non c'è altro da leggere.
            }
        }
    }

    func stop() {
        readLoop?.cancel()
        process?.terminate()
        process = nil
        stdin = nil
    }

    /// Invia un comando e aspetta la risposta corrispondente. `payload` non
    /// deve contenere "id" né "cmd": li aggiunge questo metodo.
    @discardableResult
    func send(_ cmd: String, _ payload: [String: JSONValue] = [:]) async throws -> JSONValue {
        guard let stdin else { throw BridgeError(message: "motore Python non avviato") }

        nextID += 1
        let id = nextID
        var object = payload
        object["id"] = .int(id)
        object["cmd"] = .string(cmd)

        let data = try JSONEncoder().encode(JSONValue.object(object))

        return try await withCheckedThrowingContinuation { continuation in
            pending[id] = continuation
            do {
                try stdin.write(contentsOf: data + Data([0x0A]))
            } catch {
                pending.removeValue(forKey: id)
                continuation.resume(throwing: error)
            }
        }
    }

    private func handleLine(_ line: String) {
        guard let data = line.data(using: .utf8),
              let value = try? JSONDecoder().decode(JSONValue.self, from: data),
              case .object(let obj) = value else { return }

        if obj["event"]?.stringValue == "connection" {
            if let present = obj["present"]?.boolValue {
                connectionContinuation.yield(present)
            }
            return
        }

        guard let id = obj["id"]?.intValue,
              let continuation = pending.removeValue(forKey: id) else { return }

        if obj["ok"]?.boolValue == true {
            continuation.resume(returning: value)
        } else {
            let message = obj["error"]?.stringValue ?? "errore sconosciuto dal motore"
            continuation.resume(throwing: BridgeError(message: message))
        }
    }

    /// `~/Library/Logs/ControlPad-engine.log`, lo stesso file che usa
    /// bridge.py: un solo posto dove guardare quando il pad non risponde.
    static func engineLogHandle() -> FileHandle? {
        let url = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/ControlPad-engine.log")
        if !FileManager.default.fileExists(atPath: url.path) {
            FileManager.default.createFile(atPath: url.path, contents: nil)
        }
        guard let handle = try? FileHandle(forWritingTo: url) else { return nil }
        try? handle.seekToEnd()
        return handle
    }

    /// Un'app lanciata da Finder/`open` eredita il PATH minimale di launchd
    /// (/usr/bin:/bin:/usr/sbin:/sbin), non quello della shell interattiva —
    /// quindi `env python3` qui risolverebbe al Python di sistema, che non ha
    /// hidapi installato, anche se `pip3 install hidapi` è stato fatto nel
    /// Terminal.
    ///
    /// La strada ovvia — chiedere alla shell di login quale python3 usa — è
    /// stata tolta: una shell di login esegue i file di configurazione
    /// dell'utente, quindi tocca cartelle che non c'entrano niente con noi, e
    /// basta che una di quelle sia protetta (Scrivania, Documenti) perché
    /// macOS fermi il processo su una richiesta di permesso — con l'app
    /// bloccata prima ancora di aprire la finestra. Qui si prova invece un
    /// elenco di percorsi noti e si tiene il primo che sa importare `hid`.
    private static let pythonPathKey = "enginePython3Path"

    private static let pythonCandidates = [
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
        "/usr/bin/python3",
    ]

    private static func resolvePython3Path() -> String {
        let defaults = UserDefaults.standard
        if let saved = defaults.string(forKey: pythonPathKey), canImportHID(saved) {
            return saved
        }

        var paths = pythonCandidates
        // Anche le versioni installate da python.org, dalla più recente.
        let versions = (try? FileManager.default.contentsOfDirectory(
            atPath: "/Library/Frameworks/Python.framework/Versions")) ?? []
        for version in versions.sorted(by: >) {
            paths.append("/Library/Frameworks/Python.framework/Versions/\(version)/bin/python3")
        }

        for path in paths where canImportHID(path) {
            defaults.set(path, forKey: pythonPathKey)
            return path
        }
        return "/usr/bin/python3"
    }

    /// hidapi è il vero requisito: un python3 che non lo importa non ci serve,
    /// e provarlo qui evita di scoprirlo dopo, con il motore che muore
    /// all'avvio senza dire perché.
    private static func canImportHID(_ path: String) -> Bool {
        guard FileManager.default.isExecutableFile(atPath: path) else { return false }
        let probe = Process()
        probe.executableURL = URL(fileURLWithPath: path)
        probe.arguments = ["-c", "import hid"]
        probe.standardOutput = FileHandle.nullDevice
        probe.standardError = FileHandle.nullDevice
        do {
            try probe.run()
            probe.waitUntilExit()
            return probe.terminationStatus == 0
        } catch {
            return false
        }
    }

    /// In un'app pacchettizzata il motore vive in Contents/Resources/ControlPadEngine
    /// (copiato lì da scripts/make_app_bundle.sh). In sviluppo, con `swift run`,
    /// non esiste ancora un bundle: si risale dalla posizione di questo sorgente
    /// fino alla radice del progetto e si punta a ControlPadEngine/ accanto a
    /// ControlPadGUI/.
    private static func resolveEngineDirectory() -> URL {
        if let resourceURL = Bundle.main.resourceURL {
            let bundled = resourceURL.appendingPathComponent("ControlPadEngine")
            if FileManager.default.fileExists(atPath: bundled.appendingPathComponent("bridge.py").path) {
                return bundled
            }
        }

        let thisFile = URL(fileURLWithPath: #filePath)
        let packageRoot = thisFile
            .deletingLastPathComponent()   // Bridge/
            .deletingLastPathComponent()   // ControlPadGUI/ (sorgenti)
            .deletingLastPathComponent()   // Sources/
            .deletingLastPathComponent()   // ControlPadGUI/ (pacchetto)
        let projectRoot = packageRoot.deletingLastPathComponent()
        return projectRoot.appendingPathComponent("ControlPadEngine")
    }
}
