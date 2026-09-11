# Task 9: 系统分享直达 ShareReceiver

**Files:**
- 创建: `app/src/main/java/com/videodl/app/ShareReceiver.kt`
- 创建: `app/src/main/java/com/videodl/app/ui/home/HomeContract.kt`（新增，解编译依赖）
- 创建或修改: `app/src/androidTest/java/com/videodl/app/ShareReceiverTest.kt`

**Interfaces:**
- 产出 `ShareReceiver` Activity；把收到的 URL 通过 Intent 传给 MainActivity。

## 关键协调要点（读 before starting）

### EXTRA_SHARE_URL 常量不存在 — 这是你的首项任务

ShareReceiver.kt 的 brief Step 1 代码里 `import com.videodl.app.ui.home.EXTRA_SHARE_URL`，但这个常量**尚未创建**（它原计划在 Task 11 Step 1 建造 `HomeContract.kt` 时创建，但 Task 11 还未执行）。如果 ShareReceiver 用这个 import，编译会失败。

**你的首项工作**：创建 `app/src/main/java/com/videodl/app/ui/home/HomeContract.kt`，内容为：

```kotlin
package com.videodl.app.ui.home

const val EXTRA_SHARE_URL = "com.videodl.app.SHARE_URL"
```

这样 ShareReceiver 能编译通过，Task 11 未来也能直接在用这个常量。

### MainActivity 尚不存在

ShareReceiver 的代码里会 `startActivity(Intent(this, MainActivity::class.java) ...)`。`MainActivity` 要在 Task 14 才创建。当前解法：
- 保留这个引用——assembleDebug 不会因 manifest 之外的 class 引用失败（Kotlin 编译会失败！）

**修正**：为了避免 Kotlin 编译失败，ShareReceiver 里**不要直接引用 MainActivity 类**。改用 implicit Intent 跳到 manifest 里已经声明的 Activity。但 Task 1 的 manifest 只声明了 MainActivity（没有类文件），而 ShareReceiver 自身也在 manifest 里注册。

最干净的方案：ShareReceiver 启动时按动作跳到 launcher activity，不直接写类名。把 `startActivity(Intent(this, MainActivity::class.java)...)` 替换为读取 manifest 的方式——但复杂。

**推荐的实际方案**：直接保留 `MainActivity::class.java` 引用。然后让 MainActivity 作为后续任务的占位类存在即可。但这会制造 Task 10/11/12 都还没有 MainActivity 的问题。

**最佳推荐方案（按 brief 意图）**：
- ShareReceiver 只对外的 action 是接收 SEND + 跳到"主界面"
- 先用一个**隐式 Intent** 跳到 MainActivity 声明的 LAUNCHER intent-filter：

```kotlin
val forward = Intent()
forward.action = Intent.ACTION_MAIN
forward.addCategory(Intent.CATEGORY_LAUNCHER)
forward.component = android.content.ComponentName(this, "com.videodl.app.MainActivity")
forward.putExtra(EXTRA_SHARE_URL, url)
forward.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
startActivity(forward)
finish()
```

但 `component = ComponentName(this, "com.videodl.app.MainActivity")` 是字符串引用，不强制编译时依赖，能绕过 MainActivity 不存在的编译问题。

**最终推荐（最简洁且保持 brief 设计意图）**：保留 brief 原代码中 `MainActivity::class.java` 引用,**并在 ShareReceiver.kt 同级创建一个最小占位 `MainActivity.kt`**，让编译通过：

暂不——这样 Task 14 会冲突。

**CONTROLLER 决定**：Task 9 implementer 你**不需要**解决 MainActivity 不存在的问题。请这样处理：
1. 创建 HomeContract.kt（EXTRA_SHARE_URL 常量）✓ 必须
2. 写 ShareReceiver.kt，**把 `MainActivity::class.java` 引用换成字符串形式的 ComponentName** 越过编译：

```kotlin
val forward = Intent()
forward.component = android.content.ComponentName(packageName, "com.videodl.app.MainActivity")
forward.putExtra(EXTRA_SHARE_URL, url)
forward.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
startActivity(forward)
finish()
```

`packageName` 用 `this.packageName`。这样不直接 import MainActivity，编译能过。Task 14 创建 MainActivity 后仍会正常接收 extra。

这是 Task 9 的"关键点"任务中，Controller 明确指定的**授权偏离**。

- [ ] **Step 1: 写 HomeContract.kt（解编译依赖）**

```kotlin
package com.videodl.app.ui.home

const val EXTRA_SHARE_URL = "com.videodl.app.SHARE_URL"
```

- [ ] **Step 2: 写 ShareReceiver（ACTION_SEND 处理，提取 URL，用字符串 ComponentName 跳到 MainActivity 后 finish 自身）**

```kotlin
package com.videodl.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import com.videodl.app.ui.home.EXTRA_SHARE_URL

class ShareReceiver : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val shared = intent?.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString() ?: ""
        val url = extractUrl(shared)
        val forward = Intent()
        forward.component = android.content.ComponentName(packageName, "com.videodl.app.MainActivity")
        forward.putExtra(EXTRA_SHARE_URL, url)
        forward.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        startActivity(forward)
        finish()
    }

    /** 与桌面版 _extract_url_from_text 1:1 对应 */
    private fun extractUrl(text: String): String {
        val t = text.trim()
        if (t.startsWith("http")) return t.trimEnd('。', '．', '.', '，', ',', '/', '\\')
        Regex("https?://\\S+").find(t)?.let { return it.value.trimEnd('。', '．', '.', '，', ',', '/', '\\') }
        return ""
    }
}
```

- [ ] **Step 3: 写 ShareReceiver instrumented test**

`app/src/androidTest/java/com/videodl/app/ShareReceiverTest.kt` 需补齐断言。无真机运行，只做编译验证。Test 需校验 ShareReceiver 在收到 SEND intent 后 forward intent 的 EXTRA_SHARE_URL 等于抽取的 URL。可借助 `androidx.test.espresso:espresso-intents`（需 `androidTestImplementation("androidx.test.espresso:espresso-intents:3.5.1")` 依赖 — 若不在 gradle 里则加上）。

Structural test（按 brief 留结构）：
```kotlin
package com.videodl.app

import android.content.Intent
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ShareReceiverTest {
    @Test fun plainUrl_passedThrough() {
        val intent = Intent(ApplicationProvider.getApplicationContext(), ShareReceiver::class.java).apply {
            action = Intent.ACTION_SEND
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, "https://www.bilibili.com/video/BV123")
        }
        ActivityScenario.launch<ShareReceiver>(intent).use { scenario ->
            // TODO: 用 Espresso-Intents intended() 校验 forward 的 EXTRA_SHARE_URL
            // 无真机只编译验证，断言留给 Task 14 真机端到端覆盖
        }
    }
}
```

- [ ] **Step 4: 编译通过**

Run: `./gradlew :app:assembleDebug`
预期: BUILD SUCCESSFUL

- [ ] **Step 5: 提交**

```bash
git add app
git commit -m "feat: ShareReceiver ACTION_SEND -> MainActivity"
```
