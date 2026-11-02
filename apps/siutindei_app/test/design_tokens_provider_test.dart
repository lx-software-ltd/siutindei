import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:siutindei_app/config/tokens/tokens.dart';

const _brandJson = {
  'primitive': {
    'colors': {'indigo500': '#FF0000'},
  },
};

void main() {
  test('runtime token updates reach designTokensProvider', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    expect(
      container.read(designTokensProvider).semantic.color.primary,
      const Color(0xFF6366F1),
    );

    container
        .read(designTokensNotifierProvider.notifier)
        .loadFromJson(_brandJson);

    expect(
      container.read(designTokensProvider).semantic.color.primary,
      const Color(0xFFFF0000),
    );
    expect(
      container.read(tokenThemeDataProvider).colorScheme.primary,
      const Color(0xFFFF0000),
    );
  });

  test('reset restores default tokens', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final notifier = container.read(designTokensNotifierProvider.notifier);

    notifier.loadFromJson(_brandJson);
    notifier.reset();

    expect(
      container.read(designTokensProvider).semantic.color.primary,
      const Color(0xFF6366F1),
    );
  });

  test('overriding designTokensProvider pins the value', () {
    final pinned = DesignTokens.defaults();
    final container = ProviderContainer(
      overrides: [designTokensProvider.overrideWithValue(pinned)],
    );
    addTearDown(container.dispose);

    container
        .read(designTokensNotifierProvider.notifier)
        .loadFromJson(_brandJson);

    expect(container.read(designTokensProvider), same(pinned));
  });
}
