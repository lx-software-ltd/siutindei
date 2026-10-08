import 'package:amplify_auth_cognito/amplify_auth_cognito.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../config/site_links.dart';
import '../../../config/tokens/tokens.dart';
import '../../../utils/external_links.dart';
import '../../../viewmodels/auth_viewmodel.dart';

/// Login screen using design tokens.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _emailController = TextEditingController();
  final _codeController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _codeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authViewModelProvider);
    final semantic = ref.watch(semanticTokensProvider);

    // Navigate back on successful sign in
    ref.listen(authViewModelProvider, (previous, next) {
      if (next.isSignedIn && !next.isLoading) {
        Navigator.of(context).pop();
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sign In'),
        leading: IconButton(
          onPressed: () => Navigator.pop(context),
          icon: const Icon(Icons.close),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.all(semantic.spacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header
              Icon(Icons.child_care, size: 64, color: semantic.color.primary),
              SizedBox(height: semantic.spacing.md),
              Text(
                'Welcome to Siu Tin Dei',
                style: semantic.text.headlineMedium,
                textAlign: TextAlign.center,
              ),
              SizedBox(height: semantic.spacing.sm),
              Text(
                'Sign in to save favorites and get '
                'personalized recommendations',
                style: semantic.text.bodyMedium,
                textAlign: TextAlign.center,
              ),
              SizedBox(height: semantic.spacing.xl),

              // Email sign in
              if (!authState.needsChallenge) ...[
                TextField(
                  controller: _emailController,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(
                    labelText: 'Email',
                    hintText: 'Enter your email',
                    prefixIcon: Icon(Icons.email_outlined),
                  ),
                  enabled: !authState.isLoading,
                ),
                SizedBox(height: semantic.spacing.md),
                SizedBox(
                  height: 48,
                  child: ElevatedButton(
                    onPressed: authState.isLoading
                        ? null
                        : () {
                            final email = _emailController.text.trim();
                            if (email.isNotEmpty) {
                              ref
                                  .read(authViewModelProvider.notifier)
                                  .signInWithEmail(email: email);
                            }
                          },
                    child: authState.isLoading
                        ? SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: semantic.color.onPrimary,
                            ),
                          )
                        : const Text('Continue with Email'),
                  ),
                ),
              ],

              // OTP verification
              if (authState.needsChallenge) ...[
                Text(
                  'We sent a code to ${authState.pendingEmail}',
                  style: semantic.text.bodyMedium,
                  textAlign: TextAlign.center,
                ),
                SizedBox(height: semantic.spacing.md),
                TextField(
                  controller: _codeController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Verification Code',
                    hintText: 'Enter the code',
                    prefixIcon: Icon(Icons.lock_outline),
                  ),
                  enabled: !authState.isLoading,
                ),
                SizedBox(height: semantic.spacing.md),
                SizedBox(
                  height: 48,
                  child: ElevatedButton(
                    onPressed: authState.isLoading
                        ? null
                        : () {
                            final code = _codeController.text.trim();
                            if (code.isNotEmpty) {
                              ref
                                  .read(authViewModelProvider.notifier)
                                  .confirmEmailSignIn(code: code);
                            }
                          },
                    child: authState.isLoading
                        ? SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: semantic.color.onPrimary,
                            ),
                          )
                        : const Text('Verify'),
                  ),
                ),
              ],

              // Error message
              if (authState.errorMessage != null) ...[
                SizedBox(height: semantic.spacing.md),
                Container(
                  padding: EdgeInsets.all(semantic.spacing.md),
                  decoration: BoxDecoration(
                    color: semantic.color.errorMuted,
                    borderRadius: BorderRadius.circular(semantic.radius.md),
                  ),
                  child: Text(
                    authState.errorMessage!,
                    style: TextStyle(color: semantic.color.error),
                    textAlign: TextAlign.center,
                  ),
                ),
              ],

              SizedBox(height: semantic.spacing.xl),

              // Divider
              Row(
                children: [
                  Expanded(child: Divider(color: semantic.color.border)),
                  Padding(
                    padding: EdgeInsets.symmetric(
                      horizontal: semantic.spacing.md,
                    ),
                    child: Text('or', style: semantic.text.caption),
                  ),
                  Expanded(child: Divider(color: semantic.color.border)),
                ],
              ),

              SizedBox(height: semantic.spacing.lg),

              // Social sign in
              _SocialButton(
                onPressed: authState.isLoading
                    ? null
                    : () => ref
                          .read(authViewModelProvider.notifier)
                          .signInWithProvider(AuthProvider.google),
                icon: Icons.g_mobiledata,
                label: 'Continue with Google',
                semantic: semantic,
              ),
              SizedBox(height: semantic.spacing.sm),
              _SocialButton(
                onPressed: authState.isLoading
                    ? null
                    : () => ref
                          .read(authViewModelProvider.notifier)
                          .signInWithProvider(AuthProvider.apple),
                icon: Icons.apple,
                label: 'Continue with Apple',
                semantic: semantic,
              ),

              SizedBox(height: semantic.spacing.lg),

              // Legal notice with links to the public website
              _LegalNotice(semantic: semantic),
            ],
          ),
        ),
      ),
    );
  }
}

class _LegalNotice extends StatelessWidget {
  const _LegalNotice({required this.semantic});

  final SemanticTokens semantic;

  @override
  Widget build(BuildContext context) {
    final captionStyle = semantic.text.caption;
    final linkStyle = captionStyle.copyWith(
      color: semantic.color.primary,
      decoration: TextDecoration.underline,
    );

    return Wrap(
      alignment: WrapAlignment.center,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Text('By continuing, you agree to our ', style: captionStyle),
        _LegalLink(
          label: 'Terms of Use',
          url: SiteLinks.termsOfUseUrl,
          style: linkStyle,
        ),
        Text(' and acknowledge our ', style: captionStyle),
        _LegalLink(
          label: 'Privacy Policy',
          url: SiteLinks.privacyPolicyUrl,
          style: linkStyle,
        ),
        Text('.', style: captionStyle),
      ],
    );
  }
}

class _LegalLink extends StatelessWidget {
  const _LegalLink({
    required this.label,
    required this.url,
    required this.style,
  });

  final String label;
  final String url;
  final TextStyle style;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => openExternalUrl(url),
      child: Semantics(link: true, child: Text(label, style: style)),
    );
  }
}

class _SocialButton extends StatelessWidget {
  const _SocialButton({
    required this.onPressed,
    required this.icon,
    required this.label,
    required this.semantic,
  });

  final VoidCallback? onPressed;
  final IconData icon;
  final String label;
  final SemanticTokens semantic;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          side: BorderSide(color: semantic.color.border),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 24),
            const SizedBox(width: 12),
            Text(label),
          ],
        ),
      ),
    );
  }
}
