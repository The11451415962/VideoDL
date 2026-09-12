import java.io.File
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// ============================================================
// release 签名配置
// ------------------------------------------------------------
// 密钥信息只从 local.properties 或命令行 -P 参数读，两者都不入仓库：
//   local.properties  → 已被 .gitignore 排除（AGP 本来也用它放 sdk.dir）
//   -PKEYSTORE_FILE=… → 临时构建用，适合 CI
//
// 没有密钥时**不报错**：照样能构建出 app-release-unsigned.apk，
// 这样"忘了配密钥"不会把日常构建卡死，但也不会悄悄产出没签名的包
// 冒充已签名包 —— 下面会打印一行提示说明这次是未签名构建。
//
// 生成密钥（一次性，自己执行，别人拿不到）：
//   keytool -genkey -v -storetype PKCS12 -keystore videodl-release.keystore \
//     -alias videodl -keyalg RSA -keysize 2048 -validity 10000
// 然后在 local.properties 里补：
//   KEYSTORE_FILE=videodl-release.keystore
//   KEYSTORE_PASSWORD=…
//   KEY_ALIAS=videodl
//   KEY_PASSWORD=…
// ============================================================
val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

fun signingProp(name: String): String? =
    (findProperty(name) as String?)?.takeIf { it.isNotBlank() }
        ?: localProps.getProperty(name)?.takeIf { it.isNotBlank() }

val keystoreFile: File? = signingProp("KEYSTORE_FILE")?.let { raw ->
    val f = File(raw)
    if (f.isAbsolute) f else rootProject.file(raw)
}
val hasKeystore: Boolean = keystoreFile?.exists() == true

android {
    namespace = "com.videodl.app"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.videodl.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
        ndk { abiFilters += listOf("arm64-v8a") }
    }
    signingConfigs {
        if (hasKeystore) {
            create("release") {
                storeFile = keystoreFile
                storePassword = signingProp("KEYSTORE_PASSWORD") ?: ""
                keyAlias = signingProp("KEY_ALIAS") ?: "videodl"
                keyPassword = signingProp("KEY_PASSWORD") ?: ""
            }
        }
    }
    buildTypes {
        release {
            // 故意不开混淆：proguard-rules.pro 目前是空的，而 Chaquopy 靠反射
            // 调 Python 桥、Compose/Coil 也有大量反射入口。开着混淆而没写 keep
            // 规则的直接后果是 release 包能装上但一跑就崩，而当前没有真机可验。
            // 等有真机跑通 release 之后再开混淆并补规则。
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"),
                          "proguard-rules.pro")
            signingConfigs.findByName("release")?.let { signingConfig = it }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }
    packaging {
        resources { excludes += "/META-INF/{AL2.0,LGPL2.1}" }
    }
}

// 提示故意用纯 ASCII 英文：Gradle 按 UTF-8 输出，Windows 控制台默认 GBK，
// 中文在这条最需要被看见的提示里会变成乱码。
gradle.taskGraph.whenReady {
    if (allTasks.any { it.name == "assembleRelease" || it.name == "bundleRelease" }) {
        if (hasKeystore) {
            logger.lifecycle("[signing] release keystore: ${keystoreFile?.absolutePath}")
        } else {
            logger.lifecycle(
                "[signing] No release keystore found -> producing " +
                    "app-release-unsigned.apk (NOT signed, cannot be installed). " +
                    "See the comment at the top of app/build.gradle.kts.")
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.10"
        pip { install("yt-dlp") }
    }
    productFlavors { create("main") { } }
    sourceSets { get("main").srcDir("src/main/python") }
}

// Chaquopy 会把 src/main/python 整个目录打进 APK，包括宿主 Python 生成的
// __pycache__（版本还和目标 3.10 不匹配）。不清理就会把无用的 .pyc 一起发布。
tasks.named("preBuild") {
    doFirst {
        file("src/main/python/__pycache__").deleteRecursively()
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.3")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.datastore:datastore-preferences:1.1.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    // 缩略图加载（下载列表 / 结果卡片）
    implementation("io.coil-kt:coil-compose:2.7.0")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
    testImplementation("junit:junit:4.13.2")
    // JVM 单元测试里 android.jar 的 org.json 是空壳，补一个真实实现才能测 JSON 编解码
    testImplementation("org.json:json:20240303")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation("androidx.test:runner:1.5.2")
    androidTestImplementation("androidx.test:rules:1.5.0")
}
