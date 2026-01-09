// GENERATED CODE - DO NOT MODIFY BY HAND
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'intl/messages_all.dart';

// **************************************************************************
// Generator: Flutter Intl IDE plugin
// Made by Localizely
// **************************************************************************

// ignore_for_file: non_constant_identifier_names, lines_longer_than_80_chars
// ignore_for_file: join_return_with_assignment, prefer_final_in_for_each
// ignore_for_file: avoid_redundant_argument_values, avoid_escaping_inner_quotes

class S {
  S();

  static S? _current;

  static S get current {
    assert(
      _current != null,
      'No instance of S was loaded. Try to initialize the S delegate before accessing S.current.',
    );
    return _current!;
  }

  static const AppLocalizationDelegate delegate = AppLocalizationDelegate();

  static Future<S> load(Locale locale) {
    final name = (locale.countryCode?.isEmpty ?? false)
        ? locale.languageCode
        : locale.toString();
    final localeName = Intl.canonicalizedLocale(name);
    return initializeMessages(localeName).then((_) {
      Intl.defaultLocale = localeName;
      final instance = S();
      S._current = instance;

      return instance;
    });
  }

  static S of(BuildContext context) {
    final instance = S.maybeOf(context);
    assert(
      instance != null,
      'No instance of S present in the widget tree. Did you add S.delegate in localizationsDelegates?',
    );
    return instance!;
  }

  static S? maybeOf(BuildContext context) {
    return Localizations.of<S>(context, S);
  }

  /// `Task`
  String get sidebar_task {
    return Intl.message('Task', name: 'sidebar_task', desc: '', args: []);
  }

  /// `Work`
  String get sidebar_work {
    return Intl.message('Work', name: 'sidebar_work', desc: '', args: []);
  }

  /// `Team Config`
  String get sidebar_team_config {
    return Intl.message(
      'Team Config',
      name: 'sidebar_team_config',
      desc: '',
      args: [],
    );
  }

  /// `Theme Packs`
  String get sidebar_theme_packs {
    return Intl.message(
      'Theme Packs',
      name: 'sidebar_theme_packs',
      desc: '',
      args: [],
    );
  }

  /// `Logs`
  String get sidebar_logs {
    return Intl.message('Logs', name: 'sidebar_logs', desc: '', args: []);
  }

  /// `About`
  String get sidebar_about {
    return Intl.message('About', name: 'sidebar_about', desc: '', args: []);
  }

  /// `Settings`
  String get sidebar_settings {
    return Intl.message(
      'Settings',
      name: 'sidebar_settings',
      desc: '',
      args: [],
    );
  }

  /// `Language Setting`
  String get language_setting {
    return Intl.message(
      'Language Setting',
      name: 'language_setting',
      desc: '',
      args: [],
    );
  }

  /// `Follow System`
  String get follow_system {
    return Intl.message(
      'Follow System',
      name: 'follow_system',
      desc: '',
      args: [],
    );
  }

  /// `Autostart`
  String get autostart {
    return Intl.message('Autostart', name: 'autostart', desc: '', args: []);
  }

  /// `MirrorChan CDK`
  String get mirrorchan_cdk {
    return Intl.message(
      'MirrorChan CDK',
      name: 'mirrorchan_cdk',
      desc: '',
      args: [],
    );
  }

  /// `Config Set Management`
  String get config_set_management {
    return Intl.message(
      'Config Set Management',
      name: 'config_set_management',
      desc: '',
      args: [],
    );
  }

  /// `Auto Update`
  String get auto_update {
    return Intl.message('Auto Update', name: 'auto_update', desc: '', args: []);
  }

  /// `CDK Status`
  String get cdk_status {
    return Intl.message('CDK Status', name: 'cdk_status', desc: '', args: []);
  }

  /// `Set`
  String get set {
    return Intl.message('Set', name: 'set', desc: '', args: []);
  }

  /// `Not Set`
  String get not_set {
    return Intl.message('Not Set', name: 'not_set', desc: '', args: []);
  }

  /// `Edit CDK`
  String get edit_cdk {
    return Intl.message('Edit CDK', name: 'edit_cdk', desc: '', args: []);
  }

  /// `Save Current Config`
  String get save_current_config {
    return Intl.message(
      'Save Current Config',
      name: 'save_current_config',
      desc: '',
      args: [],
    );
  }

  /// `Manage Local Configs`
  String get manage_local_configs {
    return Intl.message(
      'Manage Local Configs',
      name: 'manage_local_configs',
      desc: '',
      args: [],
    );
  }

  /// `Export Current Config`
  String get export_current_config {
    return Intl.message(
      'Export Current Config',
      name: 'export_current_config',
      desc: '',
      args: [],
    );
  }

  /// `Import To Current Config`
  String get import_to_current_config {
    return Intl.message(
      'Import To Current Config',
      name: 'import_to_current_config',
      desc: '',
      args: [],
    );
  }

  /// `Update from MirrorChan`
  String get update_from_mirrorchan {
    return Intl.message(
      'Update from MirrorChan',
      name: 'update_from_mirrorchan',
      desc: '',
      args: [],
    );
  }

  /// `Update from GitHub`
  String get update_from_github {
    return Intl.message(
      'Update from GitHub',
      name: 'update_from_github',
      desc: '',
      args: [],
    );
  }

  /// `Downloading from `
  String get downloading_from {
    return Intl.message(
      'Downloading from ',
      name: 'downloading_from',
      desc: '',
      args: [],
    );
  }

  /// ` update completed`
  String get update_completed {
    return Intl.message(
      ' update completed',
      name: 'update_completed',
      desc: '',
      args: [],
    );
  }

  /// `Edit MirrorChan CDK`
  String get edit_mirrorchan_cdk {
    return Intl.message(
      'Edit MirrorChan CDK',
      name: 'edit_mirrorchan_cdk',
      desc: '',
      args: [],
    );
  }

  /// `Enter CDK`
  String get enter_cdk {
    return Intl.message('Enter CDK', name: 'enter_cdk', desc: '', args: []);
  }

  /// `Cancel`
  String get cancel {
    return Intl.message('Cancel', name: 'cancel', desc: '', args: []);
  }

  /// `Save`
  String get save {
    return Intl.message('Save', name: 'save', desc: '', args: []);
  }

  /// `Save Config Set`
  String get save_config_set {
    return Intl.message(
      'Save Config Set',
      name: 'save_config_set',
      desc: '',
      args: [],
    );
  }

  /// `Enter Config Set Name`
  String get enter_config_set_name {
    return Intl.message(
      'Enter Config Set Name',
      name: 'enter_config_set_name',
      desc: '',
      args: [],
    );
  }

  /// `Confirm`
  String get confirm {
    return Intl.message('Confirm', name: 'confirm', desc: '', args: []);
  }

  /// `Close`
  String get close {
    return Intl.message('Close', name: 'close', desc: '', args: []);
  }

  /// `Load Config`
  String get load_config {
    return Intl.message('Load Config', name: 'load_config', desc: '', args: []);
  }

  /// `Loading config will overwrite current config, are you sure?`
  String get load_config_warning {
    return Intl.message(
      'Loading config will overwrite current config, are you sure?',
      name: 'load_config_warning',
      desc: '',
      args: [],
    );
  }

  /// `Task Config`
  String get task_config {
    return Intl.message('Task Config', name: 'task_config', desc: '', args: []);
  }

  /// `Team Config`
  String get team_config {
    return Intl.message('Team Config', name: 'team_config', desc: '', args: []);
  }

  /// `Theme Pack Config`
  String get theme_pack_config {
    return Intl.message(
      'Theme Pack Config',
      name: 'theme_pack_config',
      desc: '',
      args: [],
    );
  }

  /// `User Config`
  String get user_config {
    return Intl.message('User Config', name: 'user_config', desc: '', args: []);
  }

  /// `Config Loaded Successfully`
  String get config_loaded {
    return Intl.message(
      'Config Loaded Successfully',
      name: 'config_loaded',
      desc: '',
      args: [],
    );
  }

  /// `Confirm Delete`
  String get confirm_delete {
    return Intl.message(
      'Confirm Delete',
      name: 'confirm_delete',
      desc: '',
      args: [],
    );
  }

  /// `Are you sure you want to delete config set`
  String get confirm_delete_message {
    return Intl.message(
      'Are you sure you want to delete config set',
      name: 'confirm_delete_message',
      desc: '',
      args: [],
    );
  }

  /// `This action is irreversible.`
  String get irreversible {
    return Intl.message(
      'This action is irreversible.',
      name: 'irreversible',
      desc: '',
      args: [],
    );
  }

  /// `Delete`
  String get delete {
    return Intl.message('Delete', name: 'delete', desc: '', args: []);
  }

  /// `Deleted Successfully`
  String get delete_success {
    return Intl.message(
      'Deleted Successfully',
      name: 'delete_success',
      desc: '',
      args: [],
    );
  }

  /// `Delete Failed`
  String get delete_failed {
    return Intl.message(
      'Delete Failed',
      name: 'delete_failed',
      desc: '',
      args: [],
    );
  }

  /// `No Local Configs`
  String get no_local_configs {
    return Intl.message(
      'No Local Configs',
      name: 'no_local_configs',
      desc: '',
      args: [],
    );
  }

  /// `Exporting config will clear MirrorChan CDK to protect privacy, are you sure?`
  String get export_config_warning {
    return Intl.message(
      'Exporting config will clear MirrorChan CDK to protect privacy, are you sure?',
      name: 'export_config_warning',
      desc: '',
      args: [],
    );
  }

  /// `Importing config will overwrite current config, are you sure?`
  String get import_config_warning {
    return Intl.message(
      'Importing config will overwrite current config, are you sure?',
      name: 'import_config_warning',
      desc: '',
      args: [],
    );
  }

  /// `Select Export Directory`
  String get select_export_directory {
    return Intl.message(
      'Select Export Directory',
      name: 'select_export_directory',
      desc: '',
      args: [],
    );
  }

  /// `Config exported successfully to`
  String get config_export_success {
    return Intl.message(
      'Config exported successfully to',
      name: 'config_export_success',
      desc: '',
      args: [],
    );
  }

  /// `Config export failed`
  String get config_export_failed {
    return Intl.message(
      'Config export failed',
      name: 'config_export_failed',
      desc: '',
      args: [],
    );
  }

  /// `Select Import Config Directory`
  String get select_import_directory {
    return Intl.message(
      'Select Import Config Directory',
      name: 'select_import_directory',
      desc: '',
      args: [],
    );
  }

  /// `Selected directory is missing required config files`
  String get missing_required_files {
    return Intl.message(
      'Selected directory is missing required config files',
      name: 'missing_required_files',
      desc: '',
      args: [],
    );
  }

  /// `Config imported successfully`
  String get config_import_success {
    return Intl.message(
      'Config imported successfully',
      name: 'config_import_success',
      desc: '',
      args: [],
    );
  }

  /// `Config import failed`
  String get config_import_failed {
    return Intl.message(
      'Config import failed',
      name: 'config_import_failed',
      desc: '',
      args: [],
    );
  }

  /// `Language setting saved successfully`
  String get language_setting_saved {
    return Intl.message(
      'Language setting saved successfully',
      name: 'language_setting_saved',
      desc: '',
      args: [],
    );
  }

  /// `Autostart setting saved successfully`
  String get autostart_setting_saved {
    return Intl.message(
      'Autostart setting saved successfully',
      name: 'autostart_setting_saved',
      desc: '',
      args: [],
    );
  }

  /// `CDK saved successfully`
  String get cdk_saved {
    return Intl.message(
      'CDK saved successfully',
      name: 'cdk_saved',
      desc: '',
      args: [],
    );
  }

  /// `Config set saved successfully`
  String get config_set_saved {
    return Intl.message(
      'Config set saved successfully',
      name: 'config_set_saved',
      desc: '',
      args: [],
    );
  }

  /// `Load failed`
  String get load_failed {
    return Intl.message('Load failed', name: 'load_failed', desc: '', args: []);
  }

  /// `Search Theme Pack`
  String get search_theme_pack {
    return Intl.message(
      'Search Theme Pack',
      name: 'search_theme_pack',
      desc: '',
      args: [],
    );
  }

  /// `Weight`
  String get weight {
    return Intl.message('Weight', name: 'weight', desc: '', args: []);
  }

  /// `A-Z`
  String get alphabetical {
    return Intl.message('A-Z', name: 'alphabetical', desc: '', args: []);
  }

  /// `No theme packs available`
  String get no_theme_packs {
    return Intl.message(
      'No theme packs available',
      name: 'no_theme_packs',
      desc: '',
      args: [],
    );
  }

  /// `Connected`
  String get connected {
    return Intl.message('Connected', name: 'connected', desc: '', args: []);
  }

  /// `Connecting...`
  String get connecting {
    return Intl.message(
      'Connecting...',
      name: 'connecting',
      desc: '',
      args: [],
    );
  }

  /// `Disconnected`
  String get disconnected {
    return Intl.message(
      'Disconnected',
      name: 'disconnected',
      desc: '',
      args: [],
    );
  }

  /// `Search logs...`
  String get search_logs {
    return Intl.message(
      'Search logs...',
      name: 'search_logs',
      desc: '',
      args: [],
    );
  }

  /// `Pic Only`
  String get pic_only {
    return Intl.message('Pic Only', name: 'pic_only', desc: '', args: []);
  }

  /// `Refresh`
  String get refresh {
    return Intl.message('Refresh', name: 'refresh', desc: '', args: []);
  }

  /// `Choose a log`
  String get choose_a_log {
    return Intl.message(
      'Choose a log',
      name: 'choose_a_log',
      desc: '',
      args: [],
    );
  }

  /// `Loading`
  String get loading {
    return Intl.message('Loading', name: 'loading', desc: '', args: []);
  }

  /// `No logs match current criteria`
  String get no_logs_match_criteria {
    return Intl.message(
      'No logs match current criteria',
      name: 'no_logs_match_criteria',
      desc: '',
      args: [],
    );
  }

  /// `Image load failed`
  String get image_load_failed {
    return Intl.message(
      'Image load failed',
      name: 'image_load_failed',
      desc: '',
      args: [],
    );
  }

  /// `Path`
  String get path {
    return Intl.message('Path', name: 'path', desc: '', args: []);
  }

  /// `Please select log ZIP file`
  String get please_select_log_folder {
    return Intl.message(
      'Please select log ZIP file',
      name: 'please_select_log_folder',
      desc: '',
      args: [],
    );
  }

  /// `Invalid Log ZIP File`
  String get invalid_log_folder {
    return Intl.message(
      'Invalid Log ZIP File',
      name: 'invalid_log_folder',
      desc: '',
      args: [],
    );
  }

  /// `Log ZIP file imported successfully`
  String get log_folder_import_success {
    return Intl.message(
      'Log ZIP file imported successfully',
      name: 'log_folder_import_success',
      desc: '',
      args: [],
    );
  }

  /// `Import failed`
  String get import_failed {
    return Intl.message(
      'Import failed',
      name: 'import_failed',
      desc: '',
      args: [],
    );
  }

  /// `Exporting logs...`
  String get exporting_logs {
    return Intl.message(
      'Exporting logs...',
      name: 'exporting_logs',
      desc: '',
      args: [],
    );
  }

  /// `Importing logs...`
  String get importing_logs {
    return Intl.message(
      'Importing logs...',
      name: 'importing_logs',
      desc: '',
      args: [],
    );
  }

  /// `Importing...`
  String get importing {
    return Intl.message('Importing...', name: 'importing', desc: '', args: []);
  }

  /// `Exporting...`
  String get exporting {
    return Intl.message('Exporting...', name: 'exporting', desc: '', args: []);
  }

  /// `Cannot get log folder path`
  String get cannot_get_log_folder_path {
    return Intl.message(
      'Cannot get log folder path',
      name: 'cannot_get_log_folder_path',
      desc: '',
      args: [],
    );
  }

  /// `Source log folder does not exist`
  String get source_log_folder_not_exist {
    return Intl.message(
      'Source log folder does not exist',
      name: 'source_log_folder_not_exist',
      desc: '',
      args: [],
    );
  }

  /// `Please select save location`
  String get please_select_save_location {
    return Intl.message(
      'Please select save location',
      name: 'please_select_save_location',
      desc: '',
      args: [],
    );
  }

  /// `Log folder exported successfully`
  String get log_folder_export_success {
    return Intl.message(
      'Log folder exported successfully',
      name: 'log_folder_export_success',
      desc: '',
      args: [],
    );
  }

  /// `Export failed`
  String get export_failed {
    return Intl.message(
      'Export failed',
      name: 'export_failed',
      desc: '',
      args: [],
    );
  }

  /// `Re-import Log`
  String get reimport_log {
    return Intl.message(
      'Re-import Log',
      name: 'reimport_log',
      desc: '',
      args: [],
    );
  }

  /// `Export the Log`
  String get export_the_log {
    return Intl.message(
      'Export the Log',
      name: 'export_the_log',
      desc: '',
      args: [],
    );
  }

  /// `Import the Log`
  String get import_the_log {
    return Intl.message(
      'Import the Log',
      name: 'import_the_log',
      desc: '',
      args: [],
    );
  }

  /// `LALC log directory does not exist`
  String get lalc_log_dir_not_exist {
    return Intl.message(
      'LALC log directory does not exist',
      name: 'lalc_log_dir_not_exist',
      desc: '',
      args: [],
    );
  }

  /// `LALC logs exported successfully to: `
  String get lalc_log_export_success {
    return Intl.message(
      'LALC logs exported successfully to: ',
      name: 'lalc_log_export_success',
      desc: '',
      args: [],
    );
  }

  /// `Server`
  String get server {
    return Intl.message('Server', name: 'server', desc: '', args: []);
  }

  /// `Error`
  String get error {
    return Intl.message('Error', name: 'error', desc: '', args: []);
  }

  /// `Task Started`
  String get task_started {
    return Intl.message(
      'Task Started',
      name: 'task_started',
      desc: '',
      args: [],
    );
  }

  /// `Start`
  String get start {
    return Intl.message('Start', name: 'start', desc: '', args: []);
  }

  /// `Task Paused`
  String get task_paused {
    return Intl.message('Task Paused', name: 'task_paused', desc: '', args: []);
  }

  /// `Pause`
  String get pause {
    return Intl.message('Pause', name: 'pause', desc: '', args: []);
  }

  /// `Task Resumed`
  String get task_resumed {
    return Intl.message(
      'Task Resumed',
      name: 'task_resumed',
      desc: '',
      args: [],
    );
  }

  /// `Resume`
  String get resume {
    return Intl.message('Resume', name: 'resume', desc: '', args: []);
  }

  /// `Task Stopped`
  String get task_stopped {
    return Intl.message(
      'Task Stopped',
      name: 'task_stopped',
      desc: '',
      args: [],
    );
  }

  /// `Stop`
  String get stop {
    return Intl.message('Stop', name: 'stop', desc: '', args: []);
  }

  /// `Connect`
  String get connect {
    return Intl.message('Connect', name: 'connect', desc: '', args: []);
  }

  /// `Disconnect`
  String get disconnect {
    return Intl.message('Disconnect', name: 'disconnect', desc: '', args: []);
  }

  /// `Team Name`
  String get team_name {
    return Intl.message('Team Name', name: 'team_name', desc: '', args: []);
  }

  /// `Copy To`
  String get copy_to {
    return Intl.message('Copy To', name: 'copy_to', desc: '', args: []);
  }

  /// `SELECTED`
  String get selected {
    return Intl.message('SELECTED', name: 'selected', desc: '', args: []);
  }

  /// `Clear Selection`
  String get clear_selection {
    return Intl.message(
      'Clear Selection',
      name: 'clear_selection',
      desc: '',
      args: [],
    );
  }

  /// `Mirror Star Config`
  String get mirror_star_config {
    return Intl.message(
      'Mirror Star Config',
      name: 'mirror_star_config',
      desc: '',
      args: [],
    );
  }

  /// `Configure`
  String get configure {
    return Intl.message('Configure', name: 'configure', desc: '', args: []);
  }

  /// `Selected Stars`
  String get selected_stars {
    return Intl.message(
      'Selected Stars',
      name: 'selected_stars',
      desc: '',
      args: [],
    );
  }

  /// `Team Style`
  String get team_style {
    return Intl.message('Team Style', name: 'team_style', desc: '', args: []);
  }

  /// `Initial Ego Gifts`
  String get initial_ego_gifts {
    return Intl.message(
      'Initial Ego Gifts',
      name: 'initial_ego_gifts',
      desc: '',
      args: [],
    );
  }

  /// `Mirror Shop Heal`
  String get mirror_shop_heal {
    return Intl.message(
      'Mirror Shop Heal',
      name: 'mirror_shop_heal',
      desc: '',
      args: [],
    );
  }

  /// `Mirror Ego Gift Config`
  String get mirror_ego_gift_config {
    return Intl.message(
      'Mirror Ego Gift Config',
      name: 'mirror_ego_gift_config',
      desc: '',
      args: [],
    );
  }

  /// `Preferred Types`
  String get preferred_types {
    return Intl.message(
      'Preferred Types',
      name: 'preferred_types',
      desc: '',
      args: [],
    );
  }

  /// `Skill Replacement Config`
  String get skill_replacement_config {
    return Intl.message(
      'Skill Replacement Config',
      name: 'skill_replacement_config',
      desc: '',
      args: [],
    );
  }

  /// `Enabled Characters`
  String get enabled_characters {
    return Intl.message(
      'Enabled Characters',
      name: 'enabled_characters',
      desc: '',
      args: [],
    );
  }

  /// `Mirror Prefer Ego Gift Style`
  String get mirror_prefer_ego_gift_style {
    return Intl.message(
      'Mirror Prefer Ego Gift Style',
      name: 'mirror_prefer_ego_gift_style',
      desc: '',
      args: [],
    );
  }

  /// `Mirror Ego Gift Allow List & Block List`
  String get mirror_ego_gift_allow_block_list {
    return Intl.message(
      'Mirror Ego Gift Allow List & Block List',
      name: 'mirror_ego_gift_allow_block_list',
      desc: '',
      args: [],
    );
  }

  /// `Search Gift`
  String get search_gift {
    return Intl.message('Search Gift', name: 'search_gift', desc: '', args: []);
  }

  /// `No gift data`
  String get no_gift_data {
    return Intl.message(
      'No gift data',
      name: 'no_gift_data',
      desc: '',
      args: [],
    );
  }

  /// `Allow List`
  String get allow_list {
    return Intl.message('Allow List', name: 'allow_list', desc: '', args: []);
  }

  /// `Block List`
  String get block_list {
    return Intl.message('Block List', name: 'block_list', desc: '', args: []);
  }

  /// `Default`
  String get default_text {
    return Intl.message('Default', name: 'default_text', desc: '', args: []);
  }

  /// `Select Target Team`
  String get select_target_team {
    return Intl.message(
      'Select Target Team',
      name: 'select_target_team',
      desc: '',
      args: [],
    );
  }

  /// `Team Index`
  String get team_index {
    return Intl.message('Team Index', name: 'team_index', desc: '', args: []);
  }

  /// `Member`
  String get member {
    return Intl.message('Member', name: 'member', desc: '', args: []);
  }

  /// `Confirm Copy`
  String get confirm_copy {
    return Intl.message(
      'Confirm Copy',
      name: 'confirm_copy',
      desc: '',
      args: [],
    );
  }

  /// `It will copy`
  String get will_copy {
    return Intl.message('It will copy', name: 'will_copy', desc: '', args: []);
  }

  /// `to`
  String get to {
    return Intl.message('to', name: 'to', desc: '', args: []);
  }

  /// `Team configuration copied successfully`
  String get team_configuration_copied_successfully {
    return Intl.message(
      'Team configuration copied successfully',
      name: 'team_configuration_copied_successfully',
      desc: '',
      args: [],
    );
  }

  /// `None`
  String get none {
    return Intl.message('None', name: 'none', desc: '', args: []);
  }

  /// `Select`
  String get select {
    return Intl.message('Select', name: 'select', desc: '', args: []);
  }

  /// `No File`
  String get file_not_found {
    return Intl.message('No File', name: 'file_not_found', desc: '', args: []);
  }

  /// `Not Exist Log Dir`
  String get lalcLogDirNotExist {
    return Intl.message(
      'Not Exist Log Dir',
      name: 'lalcLogDirNotExist',
      desc: '',
      args: [],
    );
  }

  /// `Export the log successfully`
  String get lalcLogExportSuccess {
    return Intl.message(
      'Export the log successfully',
      name: 'lalcLogExportSuccess',
      desc: '',
      args: [],
    );
  }

  /// `Announcement`
  String get announcement {
    return Intl.message(
      'Announcement',
      name: 'announcement',
      desc: '',
      args: [],
    );
  }

  /// `Tutorial`
  String get tutorial {
    return Intl.message('Tutorial', name: 'tutorial', desc: '', args: []);
  }

  /// `Check how to use LALC, which even Don Quixote can read easily.`
  String get check_how_to_use_app {
    return Intl.message(
      'Check how to use LALC, which even Don Quixote can read easily.',
      name: 'check_how_to_use_app',
      desc: '',
      args: [],
    );
  }

  /// `Click to see full declaration`
  String get click_to_see_full_declaration {
    return Intl.message(
      'Click to see full declaration',
      name: 'click_to_see_full_declaration',
      desc: '',
      args: [],
    );
  }

  /// `No other configs\nJust claim all the things in the mailbox`
  String get no_other_configs_mail {
    return Intl.message(
      'No other configs\nJust claim all the things in the mailbox',
      name: 'no_other_configs_mail',
      desc: '',
      args: [],
    );
  }

  /// `No other configs\nJust claim all the coins on the task board`
  String get no_other_configs_reward {
    return Intl.message(
      'No other configs\nJust claim all the coins on the task board',
      name: 'no_other_configs_reward',
      desc: '',
      args: [],
    );
  }

  /// `Hint: This is the count lalc will purchase enkephalin with lunary today.`
  String get daily_lunacy_purchase_hint {
    return Intl.message(
      'Hint: This is the count lalc will purchase enkephalin with lunary today.',
      name: 'daily_lunacy_purchase_hint',
      desc: '',
      args: [],
    );
  }

  /// `Do Nothing`
  String get at_last_do_nothing {
    return Intl.message(
      'Do Nothing',
      name: 'at_last_do_nothing',
      desc: '',
      args: [],
    );
  }

  /// `Close LALC`
  String get at_last_close_lalc {
    return Intl.message(
      'Close LALC',
      name: 'at_last_close_lalc',
      desc: '',
      args: [],
    );
  }

  /// `Close both LALC and LimbusCompany`
  String get at_last_close_both {
    return Intl.message(
      'Close both LALC and LimbusCompany',
      name: 'at_last_close_both',
      desc: '',
      args: [],
    );
  }

  /// `Shutdown the PC`
  String get at_last_shutdown_pc {
    return Intl.message(
      'Shutdown the PC',
      name: 'at_last_shutdown_pc',
      desc: '',
      args: [],
    );
  }

  /// `Execution Count`
  String get execution_count {
    return Intl.message(
      'Execution Count',
      name: 'execution_count',
      desc: '',
      args: [],
    );
  }

  /// `Luxcavation Mode`
  String get luxcavation_mode {
    return Intl.message(
      'Luxcavation Mode',
      name: 'luxcavation_mode',
      desc: '',
      args: [],
    );
  }

  /// `Exp Stage`
  String get exp_stage {
    return Intl.message('Exp Stage', name: 'exp_stage', desc: '', args: []);
  }

  /// `Thread Stage`
  String get thread_stage {
    return Intl.message(
      'Thread Stage',
      name: 'thread_stage',
      desc: '',
      args: [],
    );
  }

  /// `Stop Purchase Gift Money`
  String get stop_purchase_gift_money {
    return Intl.message(
      'Stop Purchase Gift Money',
      name: 'stop_purchase_gift_money',
      desc: '',
      args: [],
    );
  }

  /// `Task Team Config`
  String get task_team_config {
    return Intl.message(
      'Task Team Config',
      name: 'task_team_config',
      desc: '',
      args: [],
    );
  }

  /// `Add Teams`
  String get add_teams {
    return Intl.message('Add Teams', name: 'add_teams', desc: '', args: []);
  }

  /// `No Team for now`
  String get no_team_for_now {
    return Intl.message(
      'No Team for now',
      name: 'no_team_for_now',
      desc: '',
      args: [],
    );
  }

  /// ` Config`
  String get team_config_title {
    return Intl.message(
      ' Config',
      name: 'team_config_title',
      desc: '',
      args: [],
    );
  }

  /// `Click to see more...`
  String get click_to_see_more {
    return Intl.message(
      'Click to see more...',
      name: 'click_to_see_more',
      desc: '',
      args: [],
    );
  }

  /// `Team Index: `
  String get team_index_label {
    return Intl.message(
      'Team Index: ',
      name: 'team_index_label',
      desc: '',
      args: [],
    );
  }

  /// `   Member: `
  String get member_count_label {
    return Intl.message(
      '   Member: ',
      name: 'member_count_label',
      desc: '',
      args: [],
    );
  }

  /// `  Team Style: `
  String get team_style_label {
    return Intl.message(
      '  Team Style: ',
      name: 'team_style_label',
      desc: '',
      args: [],
    );
  }

  /// `Select your Teams`
  String get select_your_teams {
    return Intl.message(
      'Select your Teams',
      name: 'select_your_teams',
      desc: '',
      args: [],
    );
  }

  /// `Cancel`
  String get cancel_button {
    return Intl.message('Cancel', name: 'cancel_button', desc: '', args: []);
  }

  /// `Latest Release`
  String get latest_release {
    return Intl.message(
      'Latest Release',
      name: 'latest_release',
      desc: '',
      args: [],
    );
  }

  /// `Published at`
  String get published_at {
    return Intl.message(
      'Published at',
      name: 'published_at',
      desc: '',
      args: [],
    );
  }

  /// `Enter`
  String get luxcavation_enter {
    return Intl.message('Enter', name: 'luxcavation_enter', desc: '', args: []);
  }

  /// `Skip Battle`
  String get luxcavation_skip_battle {
    return Intl.message(
      'Skip Battle',
      name: 'luxcavation_skip_battle',
      desc: '',
      args: [],
    );
  }

  /// `Current Version`
  String get current_version {
    return Intl.message(
      'Current Version',
      name: 'current_version',
      desc: '',
      args: [],
    );
  }

  /// `Version`
  String get version {
    return Intl.message('Version', name: 'version', desc: '', args: []);
  }

  /// `Downloading...`
  String get downloading {
    return Intl.message(
      'Downloading...',
      name: 'downloading',
      desc: '',
      args: [],
    );
  }

  /// `Auto Update Confirmation`
  String get confirm_auto_update {
    return Intl.message(
      'Auto Update Confirmation',
      name: 'confirm_auto_update',
      desc: '',
      args: [],
    );
  }

  /// `Do you want to auto-complete the overwrite update?\nNote: Configurations will not be overwritten, but logs will be lost.`
  String get auto_update_warning {
    return Intl.message(
      'Do you want to auto-complete the overwrite update?\nNote: Configurations will not be overwritten, but logs will be lost.',
      name: 'auto_update_warning',
      desc: '',
      args: [],
    );
  }

  /// `Yes, Close the software now to continue updating`
  String get yes_auto_update {
    return Intl.message(
      'Yes, Close the software now to continue updating',
      name: 'yes_auto_update',
      desc: '',
      args: [],
    );
  }

  /// `No, Let me update manually`
  String get no_manual_update {
    return Intl.message(
      'No, Let me update manually',
      name: 'no_manual_update',
      desc: '',
      args: [],
    );
  }

  /// `Update bat file path`
  String get update_bat_path {
    return Intl.message(
      'Update bat file path',
      name: 'update_bat_path',
      desc: '',
      args: [],
    );
  }

  /// `Project path`
  String get project_path {
    return Intl.message(
      'Project path',
      name: 'project_path',
      desc: '',
      args: [],
    );
  }

  /// `Update from last downloaded file`
  String get local_update {
    return Intl.message(
      'Update from last downloaded file',
      name: 'local_update',
      desc: '',
      args: [],
    );
  }

  /// `Can not connect to LALC backend`
  String get websocket_disconnected {
    return Intl.message(
      'Can not connect to LALC backend',
      name: 'websocket_disconnected',
      desc: '',
      args: [],
    );
  }

  /// `Can not find the last downloaded file(lalc)`
  String get lalc_folder_not_exist {
    return Intl.message(
      'Can not find the last downloaded file(lalc)',
      name: 'lalc_folder_not_exist',
      desc: '',
      args: [],
    );
  }

  /// `Update script executed successfully`
  String get update_script_executed {
    return Intl.message(
      'Update script executed successfully',
      name: 'update_script_executed',
      desc: '',
      args: [],
    );
  }

  /// `Update script execution failed`
  String get update_script_failed {
    return Intl.message(
      'Update script execution failed',
      name: 'update_script_failed',
      desc: '',
      args: [],
    );
  }

  /// `Update script file not found`
  String get update_script_not_found {
    return Intl.message(
      'Update script file not found',
      name: 'update_script_not_found',
      desc: '',
      args: [],
    );
  }

  /// `Statement`
  String get statement {
    return Intl.message('Statement', name: 'statement', desc: '', args: []);
  }

  /// `Daily Lunacy Purchase`
  String get daily_lunacy_purchase {
    return Intl.message(
      'Daily Lunacy Purchase',
      name: 'daily_lunacy_purchase',
      desc: '',
      args: [],
    );
  }

  /// `Mail`
  String get mail {
    return Intl.message('Mail', name: 'mail', desc: '', args: []);
  }

  /// `EXP`
  String get exp {
    return Intl.message('EXP', name: 'exp', desc: '', args: []);
  }

  /// `Thread`
  String get thread {
    return Intl.message('Thread', name: 'thread', desc: '', args: []);
  }

  /// `Mirror`
  String get mirror {
    return Intl.message('Mirror', name: 'mirror', desc: '', args: []);
  }

  /// `Reward`
  String get reward {
    return Intl.message('Reward', name: 'reward', desc: '', args: []);
  }

  /// `At Last`
  String get at_last {
    return Intl.message('At Last', name: 'at_last', desc: '', args: []);
  }

  /// `Mirror Difficulty`
  String get mirror_difficulty {
    return Intl.message(
      'Mirror Difficulty',
      name: 'mirror_difficulty',
      desc: '',
      args: [],
    );
  }

  /// `Normal`
  String get mirror_difficulty_normal {
    return Intl.message(
      'Normal',
      name: 'mirror_difficulty_normal',
      desc: '',
      args: [],
    );
  }

  /// `Hard`
  String get mirror_difficulty_hard {
    return Intl.message(
      'Hard',
      name: 'mirror_difficulty_hard',
      desc: '',
      args: [],
    );
  }

  /// `New version available!`
  String get new_version_available {
    return Intl.message(
      'New version available!',
      name: 'new_version_available',
      desc: '',
      args: [],
    );
  }

  /// `Check the announcement for details.`
  String get check_announcement_for_details {
    return Intl.message(
      'Check the announcement for details.',
      name: 'check_announcement_for_details',
      desc: '',
      args: [],
    );
  }

  /// `Task cannot start`
  String get task_start_error {
    return Intl.message(
      'Task cannot start',
      name: 'task_start_error',
      desc: '',
      args: [],
    );
  }

  /// `No team configured, please configure at least one team before starting the task.`
  String get no_team_configured {
    return Intl.message(
      'No team configured, please configure at least one team before starting the task.',
      name: 'no_team_configured',
      desc: '',
      args: [],
    );
  }

  /// `All tasks started`
  String get all_tasks_started {
    return Intl.message(
      'All tasks started',
      name: 'all_tasks_started',
      desc: '',
      args: [],
    );
  }

  /// `Light Mode`
  String get light_mode {
    return Intl.message('Light Mode', name: 'light_mode', desc: '', args: []);
  }

  /// `Dark Mode`
  String get dark_mode {
    return Intl.message('Dark Mode', name: 'dark_mode', desc: '', args: []);
  }

  /// `Missing preferred ego-gift types`
  String get no_prefer_ego_type_configured {
    return Intl.message(
      'Missing preferred ego-gift types',
      name: 'no_prefer_ego_type_configured',
      desc: '',
      args: [],
    );
  }

  /// `WebSocket not connected, please connect to server first`
  String get websocket_not_connected {
    return Intl.message(
      'WebSocket not connected, please connect to server first',
      name: 'websocket_not_connected',
      desc: '',
      args: [],
    );
  }

  /// `Task is already running`
  String get task_already_running {
    return Intl.message(
      'Task is already running',
      name: 'task_already_running',
      desc: '',
      args: [],
    );
  }

  /// `Operation failed`
  String get task_operation_failed {
    return Intl.message(
      'Operation failed',
      name: 'task_operation_failed',
      desc: '',
      args: [],
    );
  }

  /// `Task start failed`
  String get task_start_failed {
    return Intl.message(
      'Task start failed',
      name: 'task_start_failed',
      desc: '',
      args: [],
    );
  }

  /// `Task is already paused`
  String get task_already_paused {
    return Intl.message(
      'Task is already paused',
      name: 'task_already_paused',
      desc: '',
      args: [],
    );
  }

  /// `Task is already stopped`
  String get task_already_stopped {
    return Intl.message(
      'Task is already stopped',
      name: 'task_already_stopped',
      desc: '',
      args: [],
    );
  }

  /// `Mirror Shop Fuse Ego Gifts`
  String get mirror_shop_fuse_ego_gifts {
    return Intl.message(
      'Mirror Shop Fuse Ego Gifts',
      name: 'mirror_shop_fuse_ego_gifts',
      desc: '',
      args: [],
    );
  }

  /// `Mirror Shop Replace Skill & Purchase Ego Gifts`
  String get mirror_shop_replace_skill_purchase_ego_gifts {
    return Intl.message(
      'Mirror Shop Replace Skill & Purchase Ego Gifts',
      name: 'mirror_shop_replace_skill_purchase_ego_gifts',
      desc: '',
      args: [],
    );
  }

  /// `Mirror Shop Enhance Ego Gifts`
  String get mirror_shop_enhance_ego_gifts {
    return Intl.message(
      'Mirror Shop Enhance Ego Gifts',
      name: 'mirror_shop_enhance_ego_gifts',
      desc: '',
      args: [],
    );
  }

  /// `Selected Teams`
  String get selected_teams {
    return Intl.message(
      'Selected Teams',
      name: 'selected_teams',
      desc: '',
      args: [],
    );
  }

  /// `Just P`
  String get just_p {
    return Intl.message('Just P', name: 'just_p', desc: '', args: []);
  }

  /// `Semi-auto task started`
  String get semi_auto_started {
    return Intl.message(
      'Semi-auto task started',
      name: 'semi_auto_started',
      desc: '',
      args: [],
    );
  }

  /// `Mirror Dungeon Battle Fail Handle`
  String get mirror_battle_fail_handle {
    return Intl.message(
      'Mirror Dungeon Battle Fail Handle',
      name: 'mirror_battle_fail_handle',
      desc: '',
      args: [],
    );
  }

  /// `Settle rewards and let next team continue`
  String get mirror_battle_fail_option_continue_next_team {
    return Intl.message(
      'Settle rewards and let next team continue',
      name: 'mirror_battle_fail_option_continue_next_team',
      desc: '',
      args: [],
    );
  }

  /// `Download completed, unzipping...`
  String get unzipping_after_download {
    return Intl.message(
      'Download completed, unzipping...',
      name: 'unzipping_after_download',
      desc: '',
      args: [],
    );
  }
}

class AppLocalizationDelegate extends LocalizationsDelegate<S> {
  const AppLocalizationDelegate();

  List<Locale> get supportedLocales {
    return const <Locale>[
      Locale.fromSubtags(languageCode: 'en'),
      Locale.fromSubtags(languageCode: 'zh', countryCode: 'CN'),
    ];
  }

  @override
  bool isSupported(Locale locale) => _isSupported(locale);
  @override
  Future<S> load(Locale locale) => S.load(locale);
  @override
  bool shouldReload(AppLocalizationDelegate old) => false;

  bool _isSupported(Locale locale) {
    for (var supportedLocale in supportedLocales) {
      if (supportedLocale.languageCode == locale.languageCode) {
        return true;
      }
    }
    return false;
  }
}
