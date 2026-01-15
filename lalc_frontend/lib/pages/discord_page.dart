import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

class DiscordPage extends StatelessWidget {
  const DiscordPage({super.key});

  @override
  Widget build(BuildContext context) {
    // 自动打开Discord链接
    _launchDiscordURL();
    
    return Scaffold(
      body: Center(
        child: Text(
          'Opening Discord...',
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
            color: Colors.white,
          ),
        ),
      ),
    );
  }

  Future<void> _launchDiscordURL() async {
    final Uri url = Uri.parse('https://discord.gg/bVzCuBU4bC');
    if (await canLaunchUrl(url)) {
      await launchUrl(url);
    } else {
      // 如果无法打开外部链接，则显示错误信息
      throw 'Could not launch $url';
    }
  }
}