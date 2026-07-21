import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.ticker import MaxNLocator


def save_summary_figure(
    annotated_image,
    area_labels,
    area_counts,
    length_labels,
    length_counts,
    output_path
):
    """
    Genera una figura resumen con:
    - imagen anotada
    - distribución de áreas
    - distribución de longitudes
    """
    fig = plt.figure(figsize=(10, 10))
    gs = gridspec.GridSpec(2, 2, figure=fig)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0])
    ax3 = fig.add_subplot(gs[1, 1])
    ax4 = fig.add_subplot(gs[0, 1])

    ax4.axis("off")

    ax1.set_title("TEM micrograph with Nanoparticles")
    ax1.imshow(annotated_image)
    ax1.set_yticklabels([])
    ax1.set_xticklabels([])

    ax2.set_title("Areas of the Nanoparticles")

    if area_labels and area_counts:
        ax2.bar(x=area_labels, height=area_counts)
        ax2.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax2.set_xticklabels(
            area_labels,
            rotation=45,
            ha="right",
            fontsize=9
        )

    ax2.set_ylabel("Number of nanoparticles")
    ax2.set_xlabel("Nanometers²")

    ax3.set_title("Lengths of the Nanoparticles")

    if length_labels and length_counts:
        ax3.bar(x=length_labels, height=length_counts)
        ax3.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax3.set_xticklabels(
            ax3.get_xticklabels(),
            rotation=45,
            ha="right",
            fontsize=9
        )

    ax3.set_ylabel("Number of nanoparticles")
    ax3.set_xlabel("Nanometers")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)