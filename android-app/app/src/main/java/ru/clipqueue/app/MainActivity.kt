package ru.clipqueue.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.ui.screens.AuthScreen
import ru.clipqueue.app.ui.screens.FolderDetailScreen
import ru.clipqueue.app.ui.screens.FoldersScreen
import ru.clipqueue.app.ui.screens.HomeScreen
import ru.clipqueue.app.ui.screens.ProfileScreen
import ru.clipqueue.app.ui.theme.ClipQueueTheme
import ru.clipqueue.app.ui.theme.CqBg

class MainActivity : ComponentActivity() {
    private val pendingAuthToken = mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        ingestAuthIntent(intent)
        val app = application.clipQueue()
        setContent {
            ClipQueueTheme {
                Surface(
                    modifier = Modifier
                        .fillMaxSize()
                        .safeDrawingPadding(),
                    color = CqBg,
                ) {
                    ClipQueueNav(
                        api = app.api,
                        session = app.session,
                        pendingToken = pendingAuthToken.value,
                        onTokenConsumed = { pendingAuthToken.value = null },
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        ingestAuthIntent(intent)
    }

    private fun ingestAuthIntent(intent: Intent?) {
        val data = intent?.data ?: return
        if (data.scheme == "clipqueue" && data.host == "auth") {
            val token = data.getQueryParameter("token")
            if (!token.isNullOrBlank()) {
                application.clipQueue().session.token = token
                pendingAuthToken.value = token
            }
        }
    }
}

@Composable
private fun ClipQueueNav(
    api: ApiClient,
    session: SessionStore,
    pendingToken: String?,
    onTokenConsumed: () -> Unit,
) {
    var loggedIn by remember { mutableStateOf(session.isLoggedIn) }
    if (pendingToken != null) {
        loggedIn = true
        onTokenConsumed()
    }

    if (!loggedIn) {
        AuthScreen(api, session) { loggedIn = true }
        return
    }

    val nav = rememberNavController()

    fun openFolder(folder: ListCard) {
        val id = folder.id ?: return
        val title = Uri.encode(folder.title.orEmpty())
        nav.navigate("folder/$id?title=$title")
    }

    NavHost(navController = nav, startDestination = "home") {
        composable("home") {
            HomeScreen(
                api = api,
                onOpenFolder = ::openFolder,
                onOpenFolders = { nav.navigate("folders") },
                onOpenProfile = { nav.navigate("profile") },
            )
        }
        composable("folders") {
            FoldersScreen(
                api = api,
                onBackHome = {
                    nav.navigate("home") {
                        popUpTo("home") { inclusive = true }
                    }
                },
                onOpenFolder = ::openFolder,
                onOpenProfile = { nav.navigate("profile") },
            )
        }
        composable(
            route = "folder/{id}?title={title}",
            arguments = listOf(
                navArgument("id") { type = NavType.IntType },
                navArgument("title") {
                    type = NavType.StringType
                    defaultValue = ""
                },
            ),
        ) { entry ->
            val id = entry.arguments?.getInt("id") ?: return@composable
            val title = Uri.decode(entry.arguments?.getString("title").orEmpty())
            FolderDetailScreen(
                api = api,
                folder = ListCard(id = id, title = title),
                onBack = { nav.popBackStack() },
            )
        }
        composable("profile") {
            ProfileScreen(
                api = api,
                session = session,
                onHome = {
                    nav.navigate("home") {
                        popUpTo("home") { inclusive = true }
                    }
                },
                onFolders = { nav.navigate("folders") },
                onLoggedOut = { loggedIn = false },
            )
        }
    }
}
