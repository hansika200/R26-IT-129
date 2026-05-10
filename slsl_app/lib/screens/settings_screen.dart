import 'package:flutter/material.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({Key? key}) : super(key: key);

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _offlineMode = false;
  bool _useModelB = false;
  final TextEditingController _ipController = TextEditingController(text: 'http://127.0.0.1:5000');

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Server Configuration',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: Color(0xFF00B4D8),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _ipController,
              decoration: InputDecoration(
                labelText: 'Janith Backend URL',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                filled: true,
                fillColor: const Color(0xFF1E1E2C),
              ),
            ),
            const SizedBox(height: 24),
            
            const Text(
              'Model Configuration',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: Color(0xFF00B4D8),
              ),
            ),
            const SizedBox(height: 16),
            SwitchListTile(
              title: const Text('Offline Mode (TFLite Only)'),
              subtitle: const Text('Disable backend communication'),
              value: _offlineMode,
              onChanged: (val) {
                setState(() => _offlineMode = val);
              },
              activeColor: const Color(0xFF00B4D8),
            ),
            SwitchListTile(
              title: const Text('Use Model B'),
              subtitle: const Text('Switch to experimental architecture'),
              value: _useModelB,
              onChanged: (val) {
                setState(() => _useModelB = val);
              },
              activeColor: const Color(0xFF00B4D8),
            ),
            
            const SizedBox(height: 32),
            const Center(
              child: Text(
                'SLSL AI System v1.0.0\nFinal Year Research Project',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white54),
              ),
            )
          ],
        ),
      ),
    );
  }
}
