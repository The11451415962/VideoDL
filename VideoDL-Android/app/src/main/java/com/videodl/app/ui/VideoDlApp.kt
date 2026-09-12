package com.videodl.app.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.viewmodel.compose.viewModel
import com.videodl.app.ui.downloads.DownloadsScreen
import com.videodl.app.ui.home.HomeScreen
import com.videodl.app.ui.home.HomeViewModel
import com.videodl.app.ui.settings.SettingsScreen

/** 底部导航的三个标签页（对标 YTDLnis：首页 / 下载 / 更多） */
enum class AppTab(val label: String, val icon: ImageVector) {
    Home("首页", Icons.Filled.Home),
    Downloads("下载", Icons.AutoMirrored.Filled.List),
    Settings("更多", Icons.Filled.Settings),
}

@Composable
fun VideoDlApp(
    homeVm: HomeViewModel,
    onOpenFile: (String) -> Unit,
) {
    var tabName by rememberSaveable { mutableStateOf(AppTab.Home.name) }
    val tab = runCatching { AppTab.valueOf(tabName) }.getOrDefault(AppTab.Home)

    Scaffold(
        bottomBar = {
            NavigationBar {
                AppTab.entries.forEach { entry ->
                    NavigationBarItem(
                        selected = tab == entry,
                        onClick = { tabName = entry.name },
                        icon = { Icon(entry.icon, contentDescription = entry.label) },
                        label = { Text(entry.label) },
                    )
                }
            }
        },
    ) { padding ->
        Box(Modifier.padding(padding)) {
            when (tab) {
                AppTab.Home -> HomeScreen(vm = homeVm, onOpenFile = onOpenFile)
                AppTab.Downloads -> DownloadsScreen(onOpenFile = onOpenFile)
                AppTab.Settings -> SettingsScreen(
                    vm = viewModel(),
                    onBack = { tabName = AppTab.Home.name },
                )
            }
        }
    }
}
