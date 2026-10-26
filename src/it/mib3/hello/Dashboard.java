package it.mib3.hello;

import java.awt.*;
import java.awt.event.*;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.nio.file.*;
import java.time.Instant;
import java.util.concurrent.*;
import javax.imageio.ImageIO;
import javax.swing.*;

/** Desktop-only renderer. The native MIB3 display integration is not implemented. */
public final class Dashboard extends JPanel {
    private static final long serialVersionUID = 1L;
    private static final Color BG = new Color(12, 18, 26), PANEL = new Color(22, 31, 43);
    private static final Color TEXT = new Color(237, 243, 249), MUTED = new Color(143, 162, 181);
    private static final Color BLUE = new Color(69, 187, 255), AMBER = new Color(245, 185, 79);
    private transient volatile Telemetry.Frame frame;

    Dashboard(Telemetry.Frame frame) {
        this.frame = frame;
        setPreferredSize(new Dimension(1280, 720));
        setBackground(BG);
    }

    private static void text(Graphics2D g, String value, int x, int y, int size, Color color, boolean bold) {
        g.setFont(new Font(Font.SANS_SERIF, bold ? Font.BOLD : Font.PLAIN, size));
        g.setColor(color); g.drawString(value, x, y);
    }

    private static String shortText(String value, int length) {
        return value.length() <= length ? value : value.substring(0, length - 1) + "…";
    }

    @Override protected void paintComponent(Graphics graphics) {
        super.paintComponent(graphics);
        Graphics2D g = (Graphics2D) graphics.create();
        try {
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
            double scale = Math.min(getWidth() / 1280.0, getHeight() / 720.0);
            g.translate((getWidth() - 1280 * scale) / 2, (getHeight() - 720 * scale) / 2);
            g.scale(scale, scale);
            g.setColor(BG); g.fillRect(0, 0, 1280, 720);
            Telemetry.Frame current = frame;
            text(g, "HELLO GTE", 48, 50, 17, BLUE, true);
            text(g, "Ciao mondo.", 48, 111, 46, TEXT, true);
            text(g, "Golf 8 GTE  /  parametri del veicolo", 50, 148, 19, MUTED, false);
            String freshness = current.freshness(Instant.now());
            Color statusColor = freshness.equals("recent") ? BLUE : AMBER;
            g.setColor(new Color(statusColor.getRed(), statusColor.getGreen(), statusColor.getBlue(), 22));
            g.fillRoundRect(48, 176, 1184, 49, 14, 14);
            text(g, current.status(Instant.now()), 68, 207, 18, statusColor, true);
            text(g, "SOLA LETTURA", 1060, 50, 15, MUTED, true);
            for (int i = 0; i < current.readings.size(); i++) {
                Telemetry.Reading r = current.readings.get(i);
                int x = 48 + (i % 3) * 402, y = 250 + (i / 3) * 178;
                g.setColor(PANEL); g.fillRoundRect(x, y, 380, 156, 18, 18);
                text(g, shortText(r.signal.label, 30), x + 22, y + 35, 17, MUTED, false);
                boolean usable = r.value != null && (freshness.equals("recent") || freshness.equals("demo"));
                Color valueColor = usable ? TEXT : MUTED;
                String value = r.formatted();
                text(g, value, x + 22, y + 102, 48, valueColor, true);
                g.setFont(new Font(Font.SANS_SERIF, Font.BOLD, 48));
                int valueWidth = g.getFontMetrics().stringWidth(value);
                if (r.value != null) text(g, r.signal.unit, x + 34 + valueWidth, y + 100, 22, MUTED, false);
                String detail = r.state.equals("invalid") ? "Valore o unità non validi"
                    : r.value == null ? "Non disponibile"
                    : current.simulation ? "Valore dimostrativo"
                    : freshness.equals("recent") ? "Ricevuto dalla sorgente"
                    : freshness.equals("stale") ? "Dato precedente"
                    : "Orario non verificabile";
                text(g, detail, x + 22, y + 133, 14, current.simulation ? AMBER : MUTED, false);
                if ("battery_soc".equals(r.signal.id) && r.value != null) {
                    g.setColor(new Color(44, 57, 70)); g.fillRoundRect(x + 22, y + 142, 336, 4, 4, 4);
                    g.setColor(usable ? BLUE : MUTED);
                    g.fillRoundRect(x + 22, y + 142, (int) (336 * r.value / 100.0), 4, 4, 4);
                }
            }
            g.setColor(new Color(39, 52, 67)); g.drawLine(48, 624, 1232, 624);
            text(g, shortText(current.source, 78), 48, 660, 17, MUTED, false);
            text(g, "Anteprima PC · installazione MIB3 da verificare", 48, 692, 15, MUTED, false);
            if (current.error != null) text(g, shortText(current.error, 45), 780, 660, 16, AMBER, false);
            else text(g, "Target da foto: H56 / SW 1989", 945, 692, 14, MUTED, false);
        } finally { g.dispose(); }
    }

    static void render(Telemetry.Frame frame, Path output, int width, int height) throws Exception {
        if (output.toAbsolutePath().getParent() != null) Files.createDirectories(output.toAbsolutePath().getParent());
        SwingUtilities.invokeAndWait(() -> {
            Dashboard panel = new Dashboard(frame); panel.setSize(width, height);
            BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
            Graphics2D graphics = image.createGraphics();
            try { panel.paint(graphics); }
            finally { graphics.dispose(); }
            try {
                if (!ImageIO.write(image, "png", output.toFile())) throw new IOException("Encoder PNG assente");
            } catch (IOException e) { throw new RuntimeException(e); }
        });
    }

    static void open(Telemetry.Source source) throws IOException {
        final Telemetry.Frame initial = source.read();
        SwingUtilities.invokeLater(() -> {
            Dashboard panel = new Dashboard(initial);
            JFrame window = new JFrame("Hello GTE · anteprima PC");
            window.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);
            window.setContentPane(panel); window.pack(); window.setMinimumSize(new Dimension(800, 480));
            window.setLocationRelativeTo(null); window.setVisible(true);
            ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor(r -> {
                Thread t = new Thread(r, "telemetry-read-only"); t.setDaemon(true); return t;
            });
            executor.scheduleWithFixedDelay(() -> {
                try {
                    Telemetry.Frame next = source.read();
                    SwingUtilities.invokeLater(() -> { panel.frame = next; panel.repaint(); });
                } catch (IOException e) {
                    executor.shutdown();
                    System.err.println("Acquisizione fermata: " + e.getMessage());
                    SwingUtilities.invokeLater(() -> { panel.frame = source.loggingFailure(); panel.repaint(); });
                }
            }, 2, 2, TimeUnit.SECONDS);
            Timer repaint = new Timer(1000, e -> panel.repaint()); repaint.start();
            window.addWindowListener(new WindowAdapter() {
                @Override public void windowClosed(WindowEvent e) {
                    repaint.stop();
                    executor.shutdownNow();
                    // Close behind any in-flight read, outside the Swing event thread.
                    Thread closer = new Thread(() -> {
                        try {
                            executor.awaitTermination(5, TimeUnit.SECONDS);
                            source.close();
                        } catch (IOException failure) { System.err.println("Errore chiusura logger: " + failure.getMessage()); }
                        catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); }
                    }, "diagnostic-log-window-close");
                    closer.start();
                }
            });
        });
    }
}
