import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'config/tokens/tokens.dart';
import 'features/home_wizard/screens/home_wizard_screen.dart';
import 'viewmodels/auth_viewmodel.dart';

/// Main application widget.
///
/// ## Design Token System
///
/// This app uses a hierarchical design token system:
///
/// ```
/// Primitive → Semantic → Component (Leaf)
/// ```
///
/// - **Primitive tokens**: Raw values (colors, sizes, fonts)
/// - **Semantic tokens**: Meaning (primary, error, spacing.md)
/// - **Component tokens**: Leaf tokens for specific widgets
///
/// ## Ingesting Custom Tokens
///
/// To apply a custom design:
///
/// 1. **Override at runtime**:
/// ```dart
/// ref.read(designTokensNotifierProvider.notifier).loadFromJson(brandJson);
/// ```
///
/// 2. **Load from asset**:
/// ```dart
/// final tokens = await TokenLoader.fromAsset('assets/tokens/brand.json');
/// ```
///
/// 3. **Override provider** (at startup):
/// ```dart
/// ProviderScope(
///   overrides: [designTokensProvider.overrideWithValue(customTokens)],
///   child: App(),
/// )
/// ```
class App extends ConsumerWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authViewModelProvider);
    final themeData = ref.watch(tokenThemeDataProvider);

    return MaterialApp(
      title: 'Siu Tin Dei',
      theme: themeData,
      debugShowCheckedModeBanner: false,
      home: authState.isLoading
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : const HomeWizardScreen(),
    );
  }
}
