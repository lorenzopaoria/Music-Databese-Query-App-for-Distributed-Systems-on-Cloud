<?php
session_start();

// Connessione al database
$conn = mysqli_connect("localhost", "root", "", "piattaforma_streaming_musicale");

// Query per recuperare i brani
$sql_brani = "SELECT * FROM contenuto JOIN crea_contenuto WHERE contenuto.idContenuto=crea_contenuto.idContenuto AND tipo = 0";
$result_brani = mysqli_query($conn, $sql_brani);

// Query per recuperare i podcast
$sql_podcast = "SELECT * FROM contenuto JOIN crea_contenuto WHERE contenuto.idContenuto=crea_contenuto.idContenuto AND tipo = 1";
$result_podcast = mysqli_query($conn, $sql_podcast);

// Query per recuperare le playlist dell'utente loggato
$email=$_SESSION['email'];
$user_id = $_SESSION['user_id'];
$sql_playlist = "SELECT * FROM playlist WHERE email = '$email'";
$result_playlist = mysqli_query($conn, $sql_playlist);
?>

<!DOCTYPE html>
<html>
<head>
	<meta charset="UTF-8">
	<title>Streaming Musicale - Home Premium</title>
	<link rel="stylesheet" type="text/css" href="style.css">
</head>
<body>
	<div class="container">
		<h1>Streaming Musicale - Home Premium</h1>
		<p>Benvenuto <?php echo $_SESSION['email']; ?>. Qui di seguito trovi alcuni dei nostri brani in vetrina:</p>
		<table>
		<tr>
			<th>Titolo</th>
			<th>Artista</th>
			<th>Durata</th>
		</tr>
		<?php
			// Mostra i brani
			while($row = mysqli_fetch_assoc($result_brani)){
			echo "<tr>";
			echo "<td>" . $row['nome'] . "</td>";
			echo "<td>" . $row['nomeArtista'] . "</td>";
			echo "<td>" . $row['duarata'] . "</td>";
			echo "</tr>";
			}
		?>
		</table>
		<p>Non dimenticare di dare un'occhiata anche ai nostri podcast!</p>
		<table>
		<tr>
			<th>Titolo</th>
			<th>Artista</th>
			<th>Durata</th>
		</tr>
		<?php
			// Mostra i brani
			while($row = mysqli_fetch_assoc($result_podcast)){
			echo "<tr>";
			echo "<td>" . $row['nome'] . "</td>";
			echo "<td>" . $row['nomeArtista'] . "</td>";
			echo "<td>" . $row['duarata'] . "</td>";
			echo "</tr>";
			}
		?>
		</table>
		<h2>Le tue playlist:</h2>
		<table>
		<tr>
			<th>Titolo</th>
			<th>Tracce</th>
		</tr>
		<?php
			// Mostra i brani
			while($row = mysqli_fetch_assoc($result_playlist)){
			echo "<tr>";
			echo "<td>" . $row['nomePlaylist'] . "</td>";
			echo "<td>" . $row['num_tracce_P'] . "</td>";
			echo "</tr>";
			}
		?>
		</table>
	</div>
</body>
</html>
