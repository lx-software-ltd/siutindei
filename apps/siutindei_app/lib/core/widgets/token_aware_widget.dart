import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../config/tokens/tokens.dart';

/// Base class for widgets that consume design tokens.
///
/// Performance note: Consider using `select` directly in build methods
/// for more granular rebuilds instead of watching full ComponentTokens.
///
/// Example with select (more performant):
/// ```dart
/// final cardTokens = ref.watch(componentTokensProvider.select((t) => t.card));
/// ```
abstract class TokenAwareWidget extends ConsumerWidget {
  const TokenAwareWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = ref.watch(componentTokensProvider);
    return buildWithTokens(context, ref, tokens);
  }

  /// Build the widget with access to component tokens.
  Widget buildWithTokens(
    BuildContext context,
    WidgetRef ref,
    ComponentTokens tokens,
  );
}

/// Base class for stateful widgets that consume design tokens.
abstract class TokenAwareStatefulWidget extends ConsumerStatefulWidget {
  const TokenAwareStatefulWidget({super.key});
}

/// State mixin for easy token access in stateful widgets.
///
/// Performance tip: Use `select` for granular watching:
/// ```dart
/// final cardTokens = ref.watch(componentTokensProvider.select((t) => t.card));
/// ```
mixin TokenAwareStateMixin<T extends ConsumerStatefulWidget>
    on ConsumerState<T> {
  /// Get component (leaf) tokens.
  ComponentTokens get tokens => ref.watch(componentTokensProvider);

  /// Get all design tokens.
  DesignTokens get designTokens => ref.watch(designTokensProvider);

  /// Get semantic tokens.
  SemanticTokens get semanticTokens => ref.watch(semanticTokensProvider);
}

/// Extension providing shortcuts for token access.
///
/// Performance note: These watch full providers. For better performance,
/// use `select` directly:
/// ```dart
/// ref.watch(componentTokensProvider.select((t) => t.button))
/// ```
extension TokenWidgetRefExtension on WidgetRef {
  /// Shortcut to component tokens.
  ComponentTokens get tokens => watch(componentTokensProvider);

  /// Shortcut to semantic tokens.
  SemanticTokens get semantic => watch(semanticTokensProvider);
}
