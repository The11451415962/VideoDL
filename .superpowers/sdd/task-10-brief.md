# Task 10: Material 3 主题

**Files:**
- 创建: `app/src/main/java/com/videodl/app/ui/theme/Color.kt`
- 创建: `app/src/main/java/com/videodl/app/ui/theme/Theme.kt`
- 创建: `app/src/main/java/com/videodl/app/ui/theme/Type.kt`

**Interfaces:**
- 产出 `VideoDLTheme` 可组合函数；被 Task 14 MainActivity 消费。

- [ ] **Step 1: 写 Color.kt**

```kotlin
package com.videodl.app.ui.theme

import androidx.compose.ui.graphics.Color

private val Primary = Color(0xFF2962FF)
private val Secondary = Color(0xFF585E71)

val LightColors = androidx.compose.material3.lightColorScheme(
    primary = Primary, secondary = Secondary)
val DarkColors = androidx.compose.material3.darkColorScheme(
    primary = Primary, secondary = Secondary)
```

- [ ] **Step 2: 写 Theme.kt**

```kotlin
package com.videodl.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable

@Composable
fun VideoDLTheme(content: @Composable () -> Unit) {
    val colors = if (isSystemInDarkTheme()) DarkColors else LightColors
    MaterialTheme(colorScheme = colors, typography = AppTypography, content = content)
}
```

- [ ] **Step 3: 写 Type.kt**

```kotlin
package com.videodl.app.ui.theme

import androidx.compose.material3.Typography

val AppTypography = Typography()
```

- [ ] **Step 4: 编译通过 + 提交**

Run: `./gradlew :app:compileDebugKotlin`
预期: BUILD SUCCESSFUL
```bash
git add app/src/main/java/com/videodl/app/ui/theme
git commit -m "feat: Material 3 theme (light + dark)"
```
