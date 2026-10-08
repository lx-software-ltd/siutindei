import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../config/tokens/tokens.dart';

/// Avatar sizes available.
enum AvatarSize { sm, md, lg }

/// Base avatar component that consumes avatar tokens.
///
/// Performance optimizations:
/// - Uses `select` for granular token watching
/// - Caches computed initials
/// - Uses ClipRRect only when needed (for images)
class BaseAvatar extends ConsumerWidget {
  const BaseAvatar({
    super.key,
    required this.name,
    this.imageUrl,
    this.size = AvatarSize.md,
  });

  final String name;
  final String? imageUrl;
  final AvatarSize size;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final avatarTokens = ref.watch(
      componentTokensProvider.select((t) => t.avatar),
    );

    final dimension = switch (size) {
      AvatarSize.sm => avatarTokens.sizeSm,
      AvatarSize.md => avatarTokens.sizeMd,
      AvatarSize.lg => avatarTokens.sizeLg,
    };

    final borderRadius = BorderRadius.circular(avatarTokens.borderRadius);

    // If no image, use simple container with initials (no clipping needed)
    if (imageUrl == null) {
      return _InitialsAvatar(
        name: name,
        dimension: dimension,
        borderRadius: borderRadius,
        tokens: avatarTokens,
      );
    }

    // With image, use ClipRRect for proper clipping
    return SizedBox(
      width: dimension,
      height: dimension,
      child: ClipRRect(
        borderRadius: borderRadius,
        child: Image.network(
          imageUrl!,
          fit: BoxFit.cover,
          // Use cacheWidth/cacheHeight for memory optimization
          cacheWidth: (dimension * MediaQuery.devicePixelRatioOf(context))
              .toInt(),
          cacheHeight: (dimension * MediaQuery.devicePixelRatioOf(context))
              .toInt(),
          errorBuilder: (context, error, stackTrace) => _InitialsAvatar(
            name: name,
            dimension: dimension,
            borderRadius: borderRadius,
            tokens: avatarTokens,
          ),
          loadingBuilder: (context, child, loadingProgress) {
            if (loadingProgress == null) return child;
            return DecoratedBox(
              decoration: BoxDecoration(
                color: avatarTokens.background,
                borderRadius: borderRadius,
              ),
              child: const SizedBox.expand(),
            );
          },
        ),
      ),
    );
  }
}

/// Initials avatar - extracted for reuse and performance.
class _InitialsAvatar extends StatelessWidget {
  const _InitialsAvatar({
    required this.name,
    required this.dimension,
    required this.borderRadius,
    required this.tokens,
  });

  final String name;
  final double dimension;
  final BorderRadius borderRadius;
  final AvatarTokens tokens;

  @override
  Widget build(BuildContext context) {
    // Compute initials once
    final initials = _computeInitials();

    return SizedBox(
      width: dimension,
      height: dimension,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: tokens.background,
          borderRadius: borderRadius,
        ),
        child: Center(
          child: Text(
            initials,
            style: TextStyle(
              color: tokens.foreground,
              fontWeight: FontWeight.w600,
              fontSize: tokens.fontSize,
            ),
          ),
        ),
      ),
    );
  }

  String _computeInitials() {
    if (name.isEmpty) return '?';
    return name
        .split(' ')
        .take(2)
        .map((e) => e.isNotEmpty ? e[0].toUpperCase() : '')
        .join();
  }
}
