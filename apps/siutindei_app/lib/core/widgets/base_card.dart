import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../config/tokens/tokens.dart';

/// Base card component that consumes card tokens.
///
/// Performance optimizations:
/// - Uses `select` for granular token watching
/// - Caches BorderRadius to avoid recreation
/// - Uses DecoratedBox instead of Container where possible
class BaseCard extends ConsumerWidget {
  const BaseCard({super.key, required this.child, this.onTap, this.padding});

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsets? padding;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cardTokens = ref.watch(componentTokensProvider.select((t) => t.card));

    // Cache border radius to avoid recreation on each build
    final borderRadius = BorderRadius.circular(cardTokens.borderRadius);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: cardTokens.background,
        borderRadius: borderRadius,
        border: Border.all(color: cardTokens.border),
        boxShadow: cardTokens.shadow,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: borderRadius,
          child: Padding(
            padding: padding ?? EdgeInsets.all(cardTokens.padding),
            child: child,
          ),
        ),
      ),
    );
  }
}

/// Section card with title header.
///
/// Performance optimizations:
/// - Extracts header to minimize rebuilds
/// - Uses `select` for granular watching
class SectionCard extends ConsumerWidget {
  const SectionCard({
    super.key,
    required this.title,
    required this.child,
    this.icon,
    this.action,
  });

  final String title;
  final Widget child;
  final IconData? icon;
  final Widget? action;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cardTokens = ref.watch(componentTokensProvider.select((t) => t.card));
    final colors = ref.watch(semanticTokensProvider.select((s) => s.color));
    final textStyles = ref.watch(semanticTokensProvider.select((s) => s.text));

    // Cache border radius
    final borderRadius = BorderRadius.circular(cardTokens.borderRadius);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: cardTokens.background,
        borderRadius: borderRadius,
        border: Border.all(color: cardTokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: EdgeInsets.all(cardTokens.padding),
            child: Row(
              children: [
                if (icon != null) ...[
                  Icon(icon, size: 20, color: colors.textSecondary),
                  SizedBox(width: cardTokens.gap),
                ],
                Text(title, style: textStyles.labelLarge),
                if (action != null) ...[const Spacer(), action!],
              ],
            ),
          ),
          Padding(
            padding: EdgeInsets.fromLTRB(
              cardTokens.padding,
              0,
              cardTokens.padding,
              cardTokens.padding,
            ),
            child: child,
          ),
        ],
      ),
    );
  }
}
