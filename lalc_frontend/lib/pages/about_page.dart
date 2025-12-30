import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:url_launcher/url_launcher.dart';

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      // title: 'About',
      theme: ThemeData.light(),
      darkTheme: ThemeData.dark(),
      home: const AboutPage(),
    );
  }
}

class AboutPage extends StatefulWidget {
  const AboutPage({super.key});
  @override
  State<AboutPage> createState() => _AboutPageState();
}

class _AboutPageState extends State<AboutPage> {
  String _md = '';

  @override
  void initState() {
    super.initState();
    _loadAsset();
  }

  Future<void> _loadAsset() async {
    String content = await rootBundle.loadString('assets/doc/README.md');

    // 去掉 <div align="center"> 和 </div> 这两种整行
    content = content
        .split('\n')
        .where((line) =>
            line.trim() != '<div align="center">' &&
            line.trim() != '</div>')
        .join('\n');

    if (mounted) setState(() => _md = content);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      // appBar: AppBar(title: const Text('About')),
      body: _md.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : _buildMarkdown(),
    );
  }

  Widget _buildMarkdown() {
  return Markdown(
    data: _md,
    onTapLink: (text, href, title) async {
      final uri = Uri.tryParse(href ?? '');
      if (uri != null && await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      }
    },
    sizedImageBuilder: (MarkdownImageConfig config) {
      final url = config.uri.toString();

      // 只渲染本地图片
      if (url.startsWith('/img/')) {
        return Image.asset('assets/doc$url', fit: BoxFit.contain);
      }

      // 其它一律跳过（不显示）
      return const SizedBox.shrink();
    },
  );
}
}