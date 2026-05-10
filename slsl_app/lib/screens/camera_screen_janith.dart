import 'dart:ui';
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:http/http.dart' as http;
import 'package:permission_handler/permission_handler.dart';
import '../constants.dart';

enum DetectionMode { modelB, modelA, comparison }

class CameraScreen extends StatefulWidget {
  const CameraScreen({super.key});
  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen>
    with WidgetsBindingObserver {

  CameraController? _cameraController;
  List<CameraDescription> _cameras = [];
  bool _isCameraReady = false;
  bool _isFrontCamera = false;

  bool _isCapturing  = false;
  bool _isProcessing = false;
  bool _serverOnline = false;

  DetectionMode _mode = DetectionMode.modelB;

  final List<Uint8List> _rawFrames = [];

  DetectionResult?  _lastResult;
  ComparisonResult? _comparisonResult;
  String _statusText      = 'Connecting to server...';
  double _captureProgress = 0.0;
  int    _countdown       = 3;

  // ── Capture config ───────────────────────────
  static const int kCaptureFrames     = 15;
  static const int kFrameIntervalMs   = 130;
  static const int kParallelBatchSize = 2;  // Reduced for thread-safe MediaPipe

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initAll();
  }

  Future<void> _initAll() async {
    await _checkServer();
    await _initCamera();
  }

  // ════════════════════════════════════════════
  // SERVER
  // ════════════════════════════════════════════
  Future<void> _checkServer() async {
    try {
      final res = await http
          .get(Uri.parse('$kServerUrl/health'))
          .timeout(const Duration(seconds: 5));
      if (res.statusCode == 200) {
        setState(() { _serverOnline = true; _statusText = 'Server connected ✅'; });
      } else { _setServerOffline(); }
    } catch (_) { _setServerOffline(); }
  }

  void _setServerOffline() => setState(() {
    _serverOnline = false;
    _statusText   = 'Server offline ❌ — PC server start කරන්න';
  });

  // ════════════════════════════════════════════
  // CAMERA
  // ════════════════════════════════════════════
  Future<void> _initCamera() async {
    final status = await Permission.camera.request();
    if (!status.isGranted) {
      setState(() => _statusText = 'Camera permission denied');
      return;
    }
    try {
      _cameras = await availableCameras();
      if (_cameras.isEmpty) {
        setState(() => _statusText = 'No camera found');
        return;
      }
      await _setupCamera(_getCamera(_isFrontCamera));
    } catch (e) { setState(() => _statusText = 'Camera error: $e'); }
  }

  CameraDescription _getCamera(bool front) => _cameras.firstWhere(
    (c) => c.lensDirection ==
        (front ? CameraLensDirection.front : CameraLensDirection.back),
    orElse: () => _cameras.first,
  );

  Future<void> _setupCamera(CameraDescription camDesc) async {
    if (_cameraController != null) {
      await _cameraController!.dispose();
      _cameraController = null;
    }
    if (mounted) setState(() => _isCameraReady = false);

    _cameraController = CameraController(
      camDesc,
      ResolutionPreset.low,
      enableAudio: false,
      imageFormatGroup: ImageFormatGroup.jpeg,
    );

    try {
      await _cameraController!.initialize();
      if (!mounted) return;
      setState(() {
        _isCameraReady = true;
        _statusText = _serverOnline
            ? 'Ready — Capture button press කරන්න'
            : 'Server offline — PC server start කරන්න';
      });
    } catch (e) {
      if (mounted) setState(() => _statusText = 'Camera setup error: $e');
    }
  }

  Future<void> _switchCamera() async {
    if (_cameras.length < 2 || _isCapturing) return;
    setState(() {
      _isCapturing      = false;
      _isProcessing     = false;
      _rawFrames.clear();
      _captureProgress  = 0.0;
      _lastResult       = null;
      _comparisonResult = null;
      _isFrontCamera    = !_isFrontCamera;
    });
    await _setupCamera(_getCamera(_isFrontCamera));
  }

  // ════════════════════════════════════════════
  // CAPTURE
  // ════════════════════════════════════════════
  Future<void> _startCapture() async {
    if (_isCapturing || !_isCameraReady || !_serverOnline) return;

    setState(() {
      _isCapturing      = true;
      _rawFrames.clear();
      _captureProgress  = 0.0;
      _lastResult       = null;
      _comparisonResult = null;
      _countdown        = 2;
      _statusText       = '🖐 Sign hold කරන්න...';
    });

    Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted || !_isCapturing) { t.cancel(); return; }
      if (_countdown > 0) {
        setState(() => _countdown--);
      } else {
        t.cancel();
      }
    });

    final stopwatch = Stopwatch()..start();
    for (int i = 0; i < kCaptureFrames; i++) {
      if (!mounted || !_isCapturing) break;
      final frameStart = stopwatch.elapsedMilliseconds;

      try {
        final XFile xfile = await _cameraController!.takePicture();
        final bytes = await xfile.readAsBytes();
        _rawFrames.add(bytes);
      } catch (_) {}

      if (mounted) {
        setState(() => _captureProgress = _rawFrames.length / kCaptureFrames);
      }

      final elapsed = stopwatch.elapsedMilliseconds - frameStart;
      final wait = kFrameIntervalMs - elapsed;
      if (wait > 0 && i < kCaptureFrames - 1) {
        await Future.delayed(Duration(milliseconds: wait));
      }
    }
    stopwatch.stop();

    if (_rawFrames.isEmpty || !mounted) {
      setState(() {
        _isCapturing = false;
        _statusText  = 'No frames captured — try again';
      });
      return;
    }

    await _processFrames();
  }

  // ════════════════════════════════════════════
  // PROCESS — Parallel batches
  // FIXED: Uses growable list properly
  // ════════════════════════════════════════════
  Future<void> _processFrames() async {
    if (!mounted) return;
    setState(() {
      _isProcessing    = true;
      _captureProgress = 0.0;
      _statusText      = 'Keypoints extract කරනවා...';
    });

    // ✅ FIXED: Pre-allocate list with placeholders, set values by index
    final List<List<double>> frameBuffer = List<List<double>>.generate(
      _rawFrames.length,
      (_) => List<double>.filled(kNumKeypoints, 0.0),
      growable: true,
    );

    int handDetectedCount = 0;
    int processed = 0;

    for (int batchStart = 0;
         batchStart < _rawFrames.length;
         batchStart += kParallelBatchSize) {
      if (!mounted) return;

      final batchEnd = (batchStart + kParallelBatchSize).clamp(0, _rawFrames.length);
      final futures = <Future<_FrameResult>>[];

      for (int i = batchStart; i < batchEnd; i++) {
        futures.add(_extractKeypoints(_rawFrames[i], i));
      }

      final results = await Future.wait(futures);
      for (final r in results) {
        if (r.index < frameBuffer.length) {
          frameBuffer[r.index] = r.keypoints;  // ← Set by index
        }
        if (r.detected) handDetectedCount++;
      }

      processed = batchEnd;
      if (mounted) {
        setState(() {
          _captureProgress = processed / _rawFrames.length;
          _statusText      = 'Processing $processed/${_rawFrames.length}...';
        });
      }
    }

    // Pad to kSequenceLength (30) if needed
    while (frameBuffer.length < kSequenceLength) {
      frameBuffer.add(List<double>.filled(kNumKeypoints, 0.0));
    }

    await _runPrediction(frameBuffer, handDetectedCount);
  }

  Future<_FrameResult> _extractKeypoints(Uint8List bytes, int index) async {
    try {
      final res = await http.post(
        Uri.parse('$kServerUrl/predict_frame'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'image': base64Encode(bytes), 'frame_id': index}),
      ).timeout(const Duration(seconds: 8));

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        return _FrameResult(
          keypoints: List<double>.from(data['keypoints']),
          detected : data['hand_detected'] as bool,
          index    : index,
        );
      }
    } catch (_) {}
    return _FrameResult(
      keypoints: List<double>.filled(kNumKeypoints, 0.0),
      detected : false,
      index    : index,
    );
  }

  // ════════════════════════════════════════════
  // PREDICT
  // ════════════════════════════════════════════
  Future<void> _runPrediction(List<List<double>> frameBuffer, int handDetectedCount) async {
    if (!mounted) return;
    setState(() => _statusText = 'Sign analyze කරනවා... 🔍');

    final filterParam = _mode == DetectionMode.modelB ? 'true'
        : _mode == DetectionMode.modelA ? 'false' : 'both';

    try {
      final res = await http.post(
        Uri.parse('$kServerUrl/predict_sequence?filter=$filterParam'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'frames': frameBuffer}),
      ).timeout(const Duration(seconds: 15));

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        if (_mode == DetectionMode.comparison) {
          setState(() {
            _comparisonResult = ComparisonResult(
              validFrames: data['valid_frames'] ?? handDetectedCount,
              modelA: _parseResult(data['model_a'], handDetectedCount),
              modelB: _parseResult(data['model_b'], handDetectedCount),
            );
            _statusText = 'Comparison complete! 🎓';
          });
        } else {
          setState(() {
            _lastResult = _parseResult(data, handDetectedCount);
            _statusText = 'Sign detected! 🎉';
          });
        }
      } else {
        setState(() => _statusText = 'Server error — try again');
      }
    } catch (e) {
      print('❌ Prediction error: $e');
      if (mounted) setState(() => _statusText = 'Connection error — try again');
    } finally {
      if (mounted) {
        setState(() {
          _isCapturing     = false;
          _isProcessing    = false;
          _captureProgress = 0.0;
          _rawFrames.clear();
        });
      }
    }
  }

  DetectionResult _parseResult(Map<String, dynamic> data, int handFrames) {
    final top3 = (data['top3'] as List? ?? []).map((e) => Top3Item(
      label     : e['label'],
      sinhala   : e['sinhala'],
      confidence: (e['confidence'] as num).toDouble(),
    )).toList();
    return DetectionResult(
      label      : data['label'] ?? 'Unknown',
      sinhala    : data['sinhala'] ?? '',
      confidence : (data['confidence'] as num? ?? 0.0).toDouble(),
      top3       : top3,
      handFrames : handFrames,
      totalFrames: kCaptureFrames,
      filtered   : data['filtered'] ?? false,
    );
  }

  void _reset() {
    setState(() {
      _isCapturing      = false;
      _isProcessing     = false;
      _rawFrames.clear();
      _captureProgress  = 0.0;
      _lastResult       = null;
      _comparisonResult = null;
      _statusText       = _serverOnline
          ? 'Ready — Capture button press කරන්න'
          : 'Server offline — PC server start කරන්න';
    });
  }

  // ════════════════════════════════════════════
  // BUILD
  // ════════════════════════════════════════════
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Stack(
          children: [
            _buildCameraPreview(),
            _buildTopBar(context),
            _buildCameraToggle(),
            if (_isCapturing && !_isProcessing) _buildCaptureOverlay(),
            if (_isProcessing) _buildProcessingOverlay(),
            Align(alignment: Alignment.bottomCenter, child: _buildBottomPanel()),
          ],
        ),
      ),
    );
  }

  Widget _buildCameraPreview() {
    if (!_isCameraReady || _cameraController == null) {
      return Container(
        color: kBackground,
        child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
          const CircularProgressIndicator(color: kPrimary),
          const SizedBox(height: 16),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Text(_statusText,
                style: const TextStyle(color: Colors.white70),
                textAlign: TextAlign.center),
          ),
        ])),
      );
    }
    return SizedBox.expand(
      child: FittedBox(
        fit: BoxFit.cover,
        child: SizedBox(
          width : _cameraController!.value.previewSize!.height,
          height: _cameraController!.value.previewSize!.width,
          child : CameraPreview(_cameraController!),
        ),
      ),
    );
  }

  Widget _buildTopBar(BuildContext context) {
    return Positioned(
      top: 0, left: 0, right: 0,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter, end: Alignment.bottomCenter,
            colors: [Colors.black87, Colors.transparent],
          ),
        ),
        child: Row(children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
            onPressed: () => Navigator.pop(context),
          ),
          const Expanded(child: Text('SLSL Detection',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold))),
          Icon(Icons.circle, size: 10, color: _serverOnline ? kSuccess : kError),
          const SizedBox(width: 4),
          IconButton(
            icon: const Icon(Icons.flip_camera_android_rounded, color: Colors.white),
            onPressed: _isCapturing ? null : _switchCamera,
          ),
        ]),
      ),
    );
  }

  Widget _buildCameraToggle() {
    return Positioned(
      top: 68, left: 0, right: 0,
      child: Center(
        child: GestureDetector(
          onTap: _isCapturing ? null : _switchCamera,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 7),
            decoration: BoxDecoration(
              color: Colors.black54,
              borderRadius: BorderRadius.circular(30),
              border: Border.all(color: _isFrontCamera ? kAccent.withOpacity(0.7) : kPrimary.withOpacity(0.7)),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              _camOption(Icons.camera_rear_rounded, 'Back',  !_isFrontCamera, kPrimary),
              const SizedBox(width: 8),
              Container(width: 1, height: 18, color: Colors.white24),
              const SizedBox(width: 8),
              _camOption(Icons.camera_front_rounded, 'Front', _isFrontCamera, kAccent),
            ]),
          ),
        ),
      ),
    );
  }

  Widget _camOption(IconData icon, String label, bool active, Color color) {
    return AnimatedOpacity(
      duration: const Duration(milliseconds: 200), opacity: active ? 1.0 : 0.4,
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, color: active ? color : Colors.white54, size: 16),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(
          color: active ? color : Colors.white54, fontSize: 12,
          fontWeight: active ? FontWeight.bold : FontWeight.normal)),
      ]),
    );
  }

  Widget _buildCaptureOverlay() {
    return Positioned.fill(
      child: Container(
        decoration: BoxDecoration(border: Border.all(color: kPrimary.withOpacity(0.8), width: 3)),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          Container(
            width: 160, height: 160,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: kPrimary, width: 3),
              color: kPrimary.withOpacity(0.08),
            ),
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Text('${_rawFrames.length}',
                  style: const TextStyle(color: kPrimary, fontSize: 42, fontWeight: FontWeight.w900)),
              Text('of $kCaptureFrames frames',
                  style: const TextStyle(color: Colors.white54, fontSize: 12)),
            ]),
          ),
          const SizedBox(height: 16),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: const [
            Icon(Icons.back_hand_outlined, color: Colors.white70, size: 20),
            SizedBox(width: 8),
            Text('Sign hold කරගෙන ඉන්න',
                style: TextStyle(color: Colors.white, fontSize: 15)),
          ]),
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 60),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: _captureProgress,
                backgroundColor: Colors.white12,
                valueColor: const AlwaysStoppedAnimation(kPrimary),
                minHeight: 6,
              ),
            ),
          ),
        ]),
      ),
    );
  }

  Widget _buildProcessingOverlay() {
    return Positioned.fill(
      child: ClipRect(
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 12.0, sigmaY: 12.0),
          child: Container(
            color: Colors.black.withOpacity(0.4),
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              const CircularProgressIndicator(color: kPrimary, strokeWidth: 3),
              const SizedBox(height: 20),
              Text(_statusText,
                  style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w500),
                  textAlign: TextAlign.center),
              const SizedBox(height: 14),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 48),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: LinearProgressIndicator(
                    value: _captureProgress,
                    backgroundColor: Colors.white12,
                    valueColor: const AlwaysStoppedAnimation(kPrimary),
                    minHeight: 6,
                  ),
                ),
              ),
            ]),
          ),
        ),
      ),
    );
  }

  Widget _buildBottomPanel() {
    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10.0, sigmaY: 10.0),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 36),
          decoration: BoxDecoration(
            color: Colors.black.withOpacity(0.5),
            border: Border(top: BorderSide(color: Colors.white.withOpacity(0.1))),
          ),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        if (!_isCapturing && !_isProcessing) _buildModeSelector(),

        if (_mode == DetectionMode.comparison && _comparisonResult != null)
          _buildComparisonCard()
        else if (_lastResult != null)
          _buildResultCard(_lastResult!),

        if (_lastResult != null || _comparisonResult != null) const SizedBox(height: 10),

        if (!_isProcessing && !_isCapturing)
          Text(_statusText,
              style: const TextStyle(color: Colors.white70, fontSize: 13),
              textAlign: TextAlign.center),
        const SizedBox(height: 18),

        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          if (_lastResult != null || _comparisonResult != null || _isCapturing)
            Padding(
              padding: const EdgeInsets.only(right: 24),
              child: _circleBtn(
                icon: Icons.refresh_rounded,
                color: Colors.white24, iconColor: Colors.white70,
                onTap: _reset,
              ),
            ),

          GestureDetector(
            onTap: (_isCapturing || _isProcessing || !_serverOnline) ? null : _startCapture,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: 74, height: 74,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _isProcessing ? Colors.white24
                    : _isCapturing ? kError.withOpacity(0.8)
                    : !_serverOnline ? Colors.grey
                    : _mode == DetectionMode.comparison ? kWarning
                    : _mode == DetectionMode.modelA ? kError
                    : kPrimary,
                border: Border.all(color: Colors.white, width: 3),
                boxShadow: [BoxShadow(
                  color: (_isCapturing ? kError : kPrimary).withOpacity(0.5),
                  blurRadius: 20,
                )],
              ),
              child: Icon(
                _isProcessing ? Icons.hourglass_empty_rounded
                    : _isCapturing ? Icons.stop_rounded
                    : Icons.fiber_manual_record_rounded,
                color: Colors.white, size: 32,
              ),
            ),
          ),

          if (!_serverOnline && !_isCapturing)
            Padding(
              padding: const EdgeInsets.only(left: 24),
              child: _circleBtn(
                icon: Icons.refresh_rounded,
                color: kError.withOpacity(0.3), iconColor: kError,
                onTap: _checkServer,
              ),
            ),
        ]),
        const SizedBox(height: 8),

        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          Text(_isFrontCamera ? '📷 Front' : '📸 Back',
              style: TextStyle(color: _isFrontCamera ? kAccent : kPrimary, fontSize: 11)),
          const SizedBox(width: 12),
          Icon(Icons.circle, size: 8, color: _serverOnline ? kSuccess : kError),
          const SizedBox(width: 4),
          Text(_serverOnline ? 'Server online' : 'Server offline',
              style: TextStyle(color: _serverOnline ? kSuccess : kError, fontSize: 11)),
        ]),
        ])),
      ),
    );
  }

  Widget _buildModeSelector() {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Colors.black54, borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white12),
      ),
      child: Row(children: [
        _modeBtn(DetectionMode.modelB,     '🟢 Model B', 'With Filter', kSuccess),
        _modeBtn(DetectionMode.modelA,     '🔴 Model A', 'No Filter',   kError),
        _modeBtn(DetectionMode.comparison, '⚖️ Compare', 'A vs B',      kWarning),
      ]),
    );
  }

  Widget _modeBtn(DetectionMode mode, String title, String sub, Color color) {
    final active = _mode == mode;
    return Expanded(
      child: GestureDetector(
        onTap: _isCapturing ? null : () => setState(() {
          _mode = mode; _lastResult = null; _comparisonResult = null;
        }),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: active ? color.withOpacity(0.25) : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
            border: active ? Border.all(color: color.withOpacity(0.6)) : null,
          ),
          child: Column(children: [
            Text(title, textAlign: TextAlign.center,
                style: TextStyle(color: active ? color : Colors.white54,
                    fontSize: 11, fontWeight: active ? FontWeight.bold : FontWeight.normal)),
            Text(sub, textAlign: TextAlign.center,
                style: TextStyle(color: active ? color.withOpacity(0.8) : Colors.white30, fontSize: 9)),
          ]),
        ),
      ),
    );
  }

  Widget _buildResultCard(DetectionResult r) {
    final isHigh  = r.confidence >= kConfidenceThreshold;
    final color   = isHigh ? kSuccess : kWarning;
    final handPct = r.totalFrames > 0 ? r.handFrames / r.totalFrames : 0.0;

    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 15.0, sigmaY: 15.0),
        child: Container(
          width: double.infinity, padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.black.withOpacity(0.4), borderRadius: BorderRadius.circular(20),
            border: Border.all(color: color.withOpacity(0.6), width: 1.5),
          ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.sign_language, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(r.label,
              style: TextStyle(color: color, fontSize: 20, fontWeight: FontWeight.bold))),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: color.withOpacity(0.2), borderRadius: BorderRadius.circular(20),
              border: Border.all(color: color.withOpacity(0.5)),
            ),
            child: Text('${(r.confidence * 100).toStringAsFixed(1)}%',
                style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 13)),
          ),
        ]),
        const SizedBox(height: 8),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(color: kSurface.withOpacity(0.6), borderRadius: BorderRadius.circular(10)),
          child: Row(children: [
            const Text('🇱🇰 ', style: TextStyle(fontSize: 16)),
            Expanded(child: Text(r.sinhala,
                style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold, height: 1.3))),
          ]),
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: r.confidence, backgroundColor: Colors.white12,
            valueColor: AlwaysStoppedAnimation(color), minHeight: 4,
          ),
        ),
        const SizedBox(height: 6),
        Row(children: [
          Icon(Icons.back_hand_outlined, size: 13, color: handPct > 0.5 ? kSuccess : kWarning),
          const SizedBox(width: 4),
          Text('Hand: ${r.handFrames}/${r.totalFrames}',
              style: TextStyle(color: handPct > 0.5 ? kSuccess : kWarning, fontSize: 11)),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: (r.filtered ? kSuccess : kError).withOpacity(0.2),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(r.filtered ? '🟢 Filter ON' : '🔴 Filter OFF',
                style: TextStyle(color: r.filtered ? kSuccess : kError,
                    fontSize: 10, fontWeight: FontWeight.bold)),
          ),
        ]),
        if (r.top3.length > 1) ...[
          const SizedBox(height: 8),
          const Divider(color: Colors.white12, height: 1),
          const SizedBox(height: 6),
          const Text('Other possibilities:', style: TextStyle(color: Colors.white54, fontSize: 11)),
          const SizedBox(height: 4),
          ...r.top3.skip(1).map((t) => Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(children: [
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(t.label,  style: const TextStyle(color: Colors.white60, fontSize: 12)),
                Text(t.sinhala, style: const TextStyle(color: Colors.white38, fontSize: 11)),
              ])),
              Text('${(t.confidence * 100).toStringAsFixed(1)}%',
                  style: const TextStyle(color: Colors.white38, fontSize: 12)),
            ]),
          )),
        ],
      ]),
        ),
      ),
    );
  }

  Widget _buildComparisonCard() {
    final c = _comparisonResult!;
    return Container(
      width: double.infinity, padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.92), borderRadius: BorderRadius.circular(16),
        border: Border.all(color: kWarning.withOpacity(0.5)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.science_rounded, color: kWarning, size: 18),
          const SizedBox(width: 8),
          const Text('Research Comparison',
              style: TextStyle(color: kWarning, fontSize: 15, fontWeight: FontWeight.bold)),
          const Spacer(),
          Text('${c.validFrames} valid', style: const TextStyle(color: Colors.white38, fontSize: 11)),
        ]),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: _miniCard(c.modelA, 'Model A', 'Baseline\n(No Filter)', kError)),
          const SizedBox(width: 8),
          Expanded(child: _miniCard(c.modelB, 'Model B', 'Proposed\n(With Filter)', kSuccess)),
        ]),
        const SizedBox(height: 10),
        _filterImpact(c.modelA, c.modelB),
      ]),
    );
  }

  Widget _miniCard(DetectionResult r, String name, String sub, Color color) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(name, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.bold)),
        Text(sub,  style: TextStyle(color: color.withOpacity(0.7), fontSize: 9)),
        const SizedBox(height: 6),
        Text(r.label, style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold),
            maxLines: 1, overflow: TextOverflow.ellipsis),
        Text(r.sinhala, style: const TextStyle(color: Colors.white70, fontSize: 11),
            maxLines: 1, overflow: TextOverflow.ellipsis),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: r.confidence, backgroundColor: Colors.white12,
            valueColor: AlwaysStoppedAnimation(color), minHeight: 5,
          ),
        ),
        const SizedBox(height: 4),
        Text('${(r.confidence * 100).toStringAsFixed(1)}%',
            style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold)),
      ]),
    );
  }

  Widget _filterImpact(DetectionResult a, DetectionResult b) {
    final diff   = b.confidence - a.confidence;
    final better = diff > 0;
    final same   = a.label == b.label;
    final color  = better ? kSuccess : kWarning;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Row(children: [
        Icon(better ? Icons.trending_up : Icons.trending_flat, color: color, size: 18),
        const SizedBox(width: 8),
        Expanded(child: Text(
          same
              ? 'Both agree: "${a.label}"\nFilter improved by ${(diff * 100).abs().toStringAsFixed(1)}%'
              : better
                  ? 'Filter changed: "${a.label}" → "${b.label}"\nModel B: ${(b.confidence * 100).toStringAsFixed(1)}%'
                  : 'Results differ — filter may need tuning',
          style: TextStyle(color: color, fontSize: 11, height: 1.4),
        )),
      ]),
    );
  }

  Widget _circleBtn({required IconData icon, required Color color, required Color iconColor, required VoidCallback onTap}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 52, height: 52,
        decoration: BoxDecoration(shape: BoxShape.circle, color: color),
        child: Icon(icon, color: iconColor, size: 24),
      ),
    );
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (_cameraController == null || !_cameraController!.value.isInitialized) return;
    if (state == AppLifecycleState.inactive) { _cameraController?.dispose(); }
    else if (state == AppLifecycleState.resumed) { _setupCamera(_getCamera(_isFrontCamera)); }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _cameraController?.dispose();
    super.dispose();
  }
}

class _FrameResult {
  final List<double> keypoints;
  final bool         detected;
  final int          index;
  _FrameResult({required this.keypoints, required this.detected, required this.index});
}

class DetectionResult {
  final String label, sinhala;
  final double confidence;
  final List<Top3Item> top3;
  final int handFrames, totalFrames;
  final bool filtered;
  DetectionResult({required this.label, required this.sinhala, required this.confidence,
      required this.top3, required this.handFrames, required this.totalFrames, required this.filtered});
}

class ComparisonResult {
  final int validFrames;
  final DetectionResult modelA, modelB;
  ComparisonResult({required this.validFrames, required this.modelA, required this.modelB});
}

class Top3Item {
  final String label, sinhala;
  final double confidence;
  Top3Item({required this.label, required this.sinhala, required this.confidence});
}