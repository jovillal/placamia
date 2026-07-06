import { useMemo, useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import placeholderContract from "./src/placeholderContract.json";

type DependencyStatus =
  | "Implemented"
  | "Documented-but-pending"
  | "Intentionally deferred";

type Dependency = {
  name: string;
  status: DependencyStatus;
  note: string;
};

type PlaceholderScreen = {
  id: string;
  title: string;
  section: string;
  purpose: string;
  mockState: string;
  keyActions: string[];
  dependencies: Dependency[];
};

const screens = placeholderContract.screens as PlaceholderScreen[];

export default function App() {
  const sections = useMemo(
    () => Array.from(new Set(screens.map((screen) => screen.section))),
    [],
  );
  const [selectedSection, setSelectedSection] = useState(sections[0]);
  const sectionScreens = screens.filter(
    (screen) => screen.section === selectedSection,
  );
  const [selectedScreenId, setSelectedScreenId] = useState(sectionScreens[0].id);
  const selectedScreen =
    screens.find((screen) => screen.id === selectedScreenId) ?? sectionScreens[0];

  function selectSection(section: string) {
    const firstScreen = screens.find((screen) => screen.section === section);
    setSelectedSection(section);
    setSelectedScreenId(firstScreen?.id ?? screens[0].id);
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" />
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.header}>
          <Text style={styles.eyebrow}>PlacamIA</Text>
          <Text style={styles.title}>Path A mobile placeholder</Text>
          <Text style={styles.notice}>{placeholderContract.contractNotice}</Text>
          <View style={styles.badgeRow}>
            <Text style={[styles.badge, styles.mockBadge]}>Static/mock only</Text>
            <Text style={[styles.badge, styles.boundaryBadge]}>
              No backend writes
            </Text>
          </View>
        </View>

        <View style={styles.sectionTabs}>
          {sections.map((section) => (
            <TouchableOpacity
              accessibilityRole="button"
              accessibilityState={{ selected: section === selectedSection }}
              key={section}
              onPress={() => selectSection(section)}
              style={[
                styles.sectionTab,
                section === selectedSection && styles.sectionTabSelected,
              ]}
            >
              <Text
                style={[
                  styles.sectionTabText,
                  section === selectedSection && styles.sectionTabTextSelected,
                ]}
              >
                {section}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.screenPicker}>
          {sectionScreens.map((screen) => (
            <TouchableOpacity
              accessibilityRole="button"
              accessibilityState={{ selected: screen.id === selectedScreen.id }}
              key={screen.id}
              onPress={() => setSelectedScreenId(screen.id)}
              style={[
                styles.screenButton,
                screen.id === selectedScreen.id && styles.screenButtonSelected,
              ]}
            >
              <Text
                style={[
                  styles.screenButtonText,
                  screen.id === selectedScreen.id && styles.screenButtonTextSelected,
                ]}
              >
                {screen.title}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.panel}>
          <Text style={styles.panelKicker}>{selectedScreen.section}</Text>
          <Text style={styles.panelTitle}>{selectedScreen.title}</Text>
          <Text style={styles.bodyText}>{selectedScreen.purpose}</Text>
          <Text style={styles.mockState}>{selectedScreen.mockState}</Text>

          <Text style={styles.subhead}>Key actions</Text>
          {selectedScreen.keyActions.map((action) => (
            <Text key={action} style={styles.listItem}>
              - {action}
            </Text>
          ))}

          <Text style={styles.subhead}>Backend dependency map</Text>
          {selectedScreen.dependencies.map((dependency) => (
            <View key={dependency.name} style={styles.dependencyRow}>
              <View style={styles.dependencyHeader}>
                <Text style={styles.dependencyName}>{dependency.name}</Text>
                <Text style={[styles.statusPill, statusStyle(dependency.status)]}>
                  {dependency.status}
                </Text>
              </View>
              <Text style={styles.dependencyNote}>{dependency.note}</Text>
            </View>
          ))}
        </View>

        <View style={styles.panel}>
          <Text style={styles.panelTitle}>#37 guardrails</Text>
          {placeholderContract.guardrails.map((guardrail) => (
            <Text key={guardrail} style={styles.listItem}>
              - {guardrail}
            </Text>
          ))}
        </View>

        <View style={styles.panel}>
          <Text style={styles.panelTitle}>Backend gaps kept visible</Text>
          {placeholderContract.backendGaps.map((gap) => (
            <Text key={gap} style={styles.listItem}>
              - {gap}
            </Text>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function statusStyle(status: DependencyStatus) {
  if (status === "Implemented") {
    return styles.statusImplemented;
  }
  if (status === "Documented-but-pending") {
    return styles.statusPending;
  }
  return styles.statusDeferred;
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#f7f8f5",
  },
  container: {
    gap: 16,
    padding: 18,
    paddingBottom: 40,
  },
  header: {
    gap: 8,
    paddingVertical: 8,
  },
  eyebrow: {
    color: "#506044",
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  title: {
    color: "#17211a",
    fontSize: 30,
    fontWeight: "800",
    letterSpacing: 0,
  },
  notice: {
    color: "#3d463e",
    fontSize: 15,
    lineHeight: 22,
  },
  badgeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 4,
  },
  badge: {
    borderRadius: 6,
    fontSize: 12,
    fontWeight: "700",
    overflow: "hidden",
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  mockBadge: {
    backgroundColor: "#f4d58d",
    color: "#473914",
  },
  boundaryBadge: {
    backgroundColor: "#c8ded2",
    color: "#183527",
  },
  sectionTabs: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  sectionTab: {
    backgroundColor: "#ffffff",
    borderColor: "#d5dbd0",
    borderRadius: 6,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  sectionTabSelected: {
    backgroundColor: "#1f3d2b",
    borderColor: "#1f3d2b",
  },
  sectionTabText: {
    color: "#263027",
    fontSize: 14,
    fontWeight: "700",
  },
  sectionTabTextSelected: {
    color: "#ffffff",
  },
  screenPicker: {
    gap: 8,
  },
  screenButton: {
    backgroundColor: "#ffffff",
    borderColor: "#d8ddd4",
    borderRadius: 6,
    borderWidth: 1,
    padding: 12,
  },
  screenButtonSelected: {
    backgroundColor: "#e7efe5",
    borderColor: "#6f8f74",
  },
  screenButtonText: {
    color: "#263027",
    fontSize: 15,
    fontWeight: "700",
  },
  screenButtonTextSelected: {
    color: "#17391f",
  },
  panel: {
    backgroundColor: "#ffffff",
    borderColor: "#dce1d9",
    borderRadius: 8,
    borderWidth: 1,
    gap: 10,
    padding: 16,
  },
  panelKicker: {
    color: "#657164",
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  panelTitle: {
    color: "#17211a",
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: 0,
  },
  bodyText: {
    color: "#354037",
    fontSize: 15,
    lineHeight: 22,
  },
  mockState: {
    backgroundColor: "#f7f8f5",
    borderRadius: 6,
    color: "#4a554b",
    fontSize: 14,
    fontWeight: "700",
    lineHeight: 20,
    padding: 10,
  },
  subhead: {
    color: "#17211a",
    fontSize: 16,
    fontWeight: "800",
    marginTop: 8,
  },
  listItem: {
    color: "#364338",
    fontSize: 14,
    lineHeight: 21,
  },
  dependencyRow: {
    borderTopColor: "#edf0eb",
    borderTopWidth: 1,
    gap: 6,
    paddingTop: 10,
  },
  dependencyHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    justifyContent: "space-between",
  },
  dependencyName: {
    color: "#1f2b22",
    flex: 1,
    fontSize: 14,
    fontWeight: "800",
    minWidth: 160,
  },
  dependencyNote: {
    color: "#536054",
    fontSize: 13,
    lineHeight: 19,
  },
  statusPill: {
    borderRadius: 6,
    fontSize: 11,
    fontWeight: "800",
    overflow: "hidden",
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  statusImplemented: {
    backgroundColor: "#d9eadf",
    color: "#163a23",
  },
  statusPending: {
    backgroundColor: "#fae6b8",
    color: "#5d4211",
  },
  statusDeferred: {
    backgroundColor: "#eadfe8",
    color: "#53314f",
  },
});
