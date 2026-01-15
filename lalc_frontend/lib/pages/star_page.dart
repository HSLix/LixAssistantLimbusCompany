import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

class StarPage extends StatelessWidget {
  const StarPage({super.key});

  @override
  Widget build(BuildContext context) {
    // 自动打开GitHub项目页面
    _launchStarURL();
    
    return Scaffold(
      body: Center(
        child: Text(
          'Opening GitHub Repository...',
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
            color: Colors.white,
          ),
        ),
      ),
    );
  }

  Future<void> _launchStarURL() async {
    final Uri url = Uri.parse('https://github.com/HSLix/LixAssistantLimbusCompany');
    if (await canLaunchUrl(url)) {
      await launchUrl(url);
    } else {
      // 如果无法打开外部链接，则显示错误信息
      throw 'Could not launch $url';
    }
  }
}