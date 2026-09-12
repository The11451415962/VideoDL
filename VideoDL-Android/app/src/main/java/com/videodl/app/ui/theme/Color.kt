package com.videodl.app.ui.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color

/**
 * 配色：Material 3 蓝色方案（Android 12+ 会被系统动态取色覆盖，见 Theme.kt），
 * 观感对齐 YTDLnis 那种"Material You + 蓝色主色"。
 */
private val Blue40 = Color(0xFF0058CB)
private val Blue80 = Color(0xFFADC6FF)
private val BlueGrey40 = Color(0xFF575E71)
private val BlueGrey80 = Color(0xFFBFC6DC)
private val Purple40 = Color(0xFF725572)
private val Purple80 = Color(0xFFE0B6DF)

val LightColors = lightColorScheme(
    primary = Blue40,
    secondary = BlueGrey40,
    tertiary = Purple40,
)

val DarkColors = darkColorScheme(
    primary = Blue80,
    secondary = BlueGrey80,
    tertiary = Purple80,
)
