# Review Package - Task 10

## Base: 9e1d00d  Head: d692356

## Commits
d692356 feat: Material 3 theme (light + dark)

## Diff stat
 .../app/src/main/java/com/videodl/app/ui/theme/Color.kt       | 11 +++++++++++
 .../app/src/main/java/com/videodl/app/ui/theme/Theme.kt       | 11 +++++++++++
 .../app/src/main/java/com/videodl/app/ui/theme/Type.kt        |  5 +++++
 3 files changed, 27 insertions(+)
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Color.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Color.kt
new file mode 100644
index 0000000..0096698
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Color.kt
@@ -0,0 +1,11 @@
+package com.videodl.app.ui.theme
+
+import androidx.compose.ui.graphics.Color
+
+private val Primary = Color(0xFF2962FF)
+private val Secondary = Color(0xFF585E71)
+
+val LightColors = androidx.compose.material3.lightColorScheme(
+    primary = Primary, secondary = Secondary)
+val DarkColors = androidx.compose.material3.darkColorScheme(
+    primary = Primary, secondary = Secondary)
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Theme.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Theme.kt
new file mode 100644
index 0000000..e8d1545
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Theme.kt
@@ -0,0 +1,11 @@
+package com.videodl.app.ui.theme
+
+import androidx.compose.foundation.isSystemInDarkTheme
+import androidx.compose.material3.MaterialTheme
+import androidx.compose.runtime.Composable
+
+@Composable
+fun VideoDLTheme(content: @Composable () -> Unit) {
+    val colors = if (isSystemInDarkTheme()) DarkColors else LightColors
+    MaterialTheme(colorScheme = colors, typography = AppTypography, content = content)
+}
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Type.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Type.kt
new file mode 100644
index 0000000..43a4148
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Type.kt
@@ -0,0 +1,5 @@
+package com.videodl.app.ui.theme
+
+import androidx.compose.material3.Typography
+
+val AppTypography = Typography()
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Color.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Color.kt
new file mode 100644
index 0000000..0096698
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Color.kt
@@ -0,0 +1,11 @@
+package com.videodl.app.ui.theme
+
+import androidx.compose.ui.graphics.Color
+
+private val Primary = Color(0xFF2962FF)
+private val Secondary = Color(0xFF585E71)
+
+val LightColors = androidx.compose.material3.lightColorScheme(
+    primary = Primary, secondary = Secondary)
+val DarkColors = androidx.compose.material3.darkColorScheme(
+    primary = Primary, secondary = Secondary)
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Theme.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Theme.kt
new file mode 100644
index 0000000..e8d1545
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Theme.kt
@@ -0,0 +1,11 @@
+package com.videodl.app.ui.theme
+
+import androidx.compose.foundation.isSystemInDarkTheme
+import androidx.compose.material3.MaterialTheme
+import androidx.compose.runtime.Composable
+
+@Composable
+fun VideoDLTheme(content: @Composable () -> Unit) {
+    val colors = if (isSystemInDarkTheme()) DarkColors else LightColors
+    MaterialTheme(colorScheme = colors, typography = AppTypography, content = content)
+}
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Type.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Type.kt
new file mode 100644
index 0000000..43a4148
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/theme/Type.kt
@@ -0,0 +1,5 @@
+package com.videodl.app.ui.theme
+
+import androidx.compose.material3.Typography
+
+val AppTypography = Typography()
