import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/main_navigator.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor         : Colors.transparent,
    statusBarIconBrightness: Brightness.light,
  ));
  runApp(const SLSLApp());
}

class SLSLApp extends StatelessWidget {
  const SLSLApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title                     : 'SLSL — Sign Language App',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor : const Color(0xFF00B4D8),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: const MainNavigator(),
    );
  }
}
